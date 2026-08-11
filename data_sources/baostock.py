"""BaoStock adapter and point-in-time-safe IVOL panel preparation."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from typing import Any, Protocol

import baostock as bs
import pandas as pd

from config import BaoStockSettings
from data_sources.tushare import prepare_ivol_panel

_PIPELINE_VERSION = 2


class BaoStockDataError(RuntimeError):
    """Raised when BaoStock data cannot be acquired or prepared safely."""


class BaoStockResult(Protocol):
    error_code: str
    error_msg: str
    fields: list[str]

    def get_data(self) -> pd.DataFrame: ...

    def next(self) -> bool: ...

    def get_row_data(self) -> list[str]: ...


class BaoStockAPI(Protocol):
    def login(self) -> BaoStockResult: ...

    def logout(self) -> BaoStockResult: ...

    def query_history_k_data_plus(
        self, *args: Any, **kwargs: Any
    ) -> BaoStockResult: ...

    def query_profit_data(self, *args: Any, **kwargs: Any) -> BaoStockResult: ...


@dataclass(frozen=True)
class BaoStockBuildConfig:
    codes: tuple[str, ...]
    start_date: date
    end_date: date
    minimum_daily_observations: int = 10
    refresh: bool = False

    def __post_init__(self) -> None:
        if not self.codes:
            raise ValueError("At least one BaoStock stock code is required")
        if len(self.codes) > 50:
            raise ValueError("MVP downloads are limited to 50 selected stock codes")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        if self.minimum_daily_observations < 5:
            raise ValueError("minimum_daily_observations must be at least 5")
        invalid = [
            code for code in self.codes if not re.fullmatch(r"(?:sh|sz)\.\d{6}", code)
        ]
        if invalid:
            raise ValueError(
                "BaoStock codes must look like sh.600000 or sz.000001: "
                + ", ".join(invalid)
            )


@dataclass(frozen=True)
class BaoStockBuildResult:
    raw_path: Path
    panel_path: Path
    manifest_path: Path
    raw_rows: int
    panel_rows: int
    cache_hit: bool


def _config_id(config: BaoStockBuildConfig, adjust_flag: str) -> str:
    payload = {
        "codes": sorted(config.codes),
        "start": config.start_date.isoformat(),
        "end": config.end_date.isoformat(),
        "minimum_daily_observations": config.minimum_daily_observations,
        "adjust_flag": adjust_flag,
        "pipeline_version": _PIPELINE_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


def _result_frame(result: BaoStockResult, endpoint: str) -> pd.DataFrame:
    if result.error_code != "0":
        raise BaoStockDataError(
            f"BaoStock {endpoint} failed [{result.error_code}]: {result.error_msg}"
        )
    if all(
        hasattr(result, attribute) for attribute in ("fields", "next", "get_row_data")
    ):
        rows: list[list[str]] = []
        while result.error_code == "0" and result.next():
            rows.append(result.get_row_data())
        if result.error_code != "0":
            raise BaoStockDataError(
                f"BaoStock {endpoint} cursor failed "
                f"[{result.error_code}]: {result.error_msg}"
            )
        return pd.DataFrame(rows, columns=result.fields)
    return result.get_data()


def _prepare_raw(history: pd.DataFrame, fundamentals: pd.DataFrame) -> pd.DataFrame:
    required_history = {
        "date",
        "code",
        "close",
        "pctChg",
        "pbMRQ",
        "tradestatus",
        "isST",
    }
    missing_history = sorted(required_history - set(history.columns))
    if missing_history:
        raise BaoStockDataError(
            "BaoStock history omitted fields: " + ", ".join(missing_history)
        )
    required_fundamentals = {"code", "pubDate", "totalShare"}
    missing_fundamentals = sorted(required_fundamentals - set(fundamentals.columns))
    if missing_fundamentals:
        raise BaoStockDataError(
            "BaoStock profit data omitted fields: " + ", ".join(missing_fundamentals)
        )

    daily = history.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    daily["close"] = pd.to_numeric(daily["close"], errors="coerce")
    daily = daily.loc[daily["tradestatus"].astype(str) == "1"]
    if daily["date"].isna().any():
        raise BaoStockDataError("BaoStock returned unparseable history dates")

    financials = fundamentals.copy()
    financials["pubDate"] = pd.to_datetime(financials["pubDate"], errors="coerce")
    financials["totalShare"] = pd.to_numeric(financials["totalShare"], errors="coerce")
    financials = financials.dropna(subset=["pubDate", "totalShare"])
    financials = financials.loc[financials["totalShare"] > 0]
    if financials.empty:
        raise BaoStockDataError(
            "BaoStock returned no published total-share observations; size cannot "
            "be constructed without inventing a proxy"
        )

    merged_frames: list[pd.DataFrame] = []
    for code, code_daily in daily.groupby("code"):
        code_fundamentals = financials.loc[financials["code"] == code]
        if code_fundamentals.empty:
            continue
        merged_frames.append(
            pd.merge_asof(
                code_daily.sort_values("date"),
                code_fundamentals.sort_values("pubDate"),
                left_on="date",
                right_on="pubDate",
                by="code",
                direction="backward",
                allow_exact_matches=True,
            )
        )
    if not merged_frames:
        raise BaoStockDataError("No history could be matched to published share data")
    merged = pd.concat(merged_frames, ignore_index=True)
    merged = merged.dropna(subset=["totalShare"])
    merged["total_mv"] = merged["close"] * merged["totalShare"]
    merged = merged.rename(
        columns={
            "code": "ts_code",
            "date": "trade_date",
            "pctChg": "pct_chg",
            "pbMRQ": "pb",
            "turn": "turnover_rate",
        }
    )
    merged["trade_date"] = merged["trade_date"].dt.strftime("%Y%m%d")
    return merged


class BaoStockIVOLDataBuilder:
    """Download selected A-share histories and cache a research-ready panel."""

    def __init__(
        self,
        settings: BaoStockSettings,
        api: BaoStockAPI | None = None,
    ) -> None:
        self.settings = settings
        self.api = api or bs

    def _login(self) -> None:
        login = self.api.login()
        if login.error_code != "0":
            raise BaoStockDataError(
                f"BaoStock login failed [{login.error_code}]: {login.error_msg}"
            )

    def _query_with_retry(
        self,
        query: Callable[[], BaoStockResult],
        endpoint: str,
        *,
        max_attempts: int = 4,
    ) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return _result_frame(query(), endpoint)
            except Exception as exc:
                last_error = exc
                if attempt == max_attempts:
                    break
                try:
                    self.api.logout()
                except Exception:
                    pass
                time.sleep(0.5 * attempt)
                self._login()
        raise BaoStockDataError(
            f"BaoStock {endpoint} failed after {max_attempts} attempts"
        ) from last_error

    def build(self, config: BaoStockBuildConfig) -> BaoStockBuildResult:
        cache_directory = self.settings.cache_directory
        cache_directory.mkdir(parents=True, exist_ok=True)
        identifier = _config_id(config, self.settings.adjust_flag)
        raw_path = cache_directory / f"ivol_daily_{identifier}.parquet"
        panel_path = cache_directory / f"ivol_panel_{identifier}.parquet"
        manifest_path = cache_directory / f"ivol_manifest_{identifier}.json"
        if (
            raw_path.exists()
            and panel_path.exists()
            and manifest_path.exists()
            and not config.refresh
        ):
            return BaoStockBuildResult(
                raw_path=raw_path,
                panel_path=panel_path,
                manifest_path=manifest_path,
                raw_rows=len(pd.read_parquet(raw_path)),
                panel_rows=len(pd.read_parquet(panel_path)),
                cache_hit=True,
            )

        self._login()
        try:
            histories: list[pd.DataFrame] = []
            fundamentals: list[pd.DataFrame] = []
            history_fields = (
                "date,code,open,high,low,close,preclose,volume,amount,adjustflag,"
                "turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST"
            )
            for code in config.codes:
                histories.append(
                    self._query_with_retry(
                        partial(
                            self.api.query_history_k_data_plus,
                            code,
                            history_fields,
                            start_date=config.start_date.isoformat(),
                            end_date=config.end_date.isoformat(),
                            frequency="d",
                            adjustflag=self.settings.adjust_flag,
                        ),
                        "query_history_k_data_plus",
                    )
                )
                for year in range(config.start_date.year - 1, config.end_date.year + 1):
                    for quarter in range(1, 5):
                        frame = self._query_with_retry(
                            partial(
                                self.api.query_profit_data,
                                code=code,
                                year=year,
                                quarter=quarter,
                            ),
                            "query_profit_data",
                        )
                        if not frame.empty:
                            fundamentals.append(frame)
        finally:
            self.api.logout()

        history = pd.concat(histories, ignore_index=True)
        if history.empty:
            raise BaoStockDataError("BaoStock returned no daily observations")
        if not fundamentals:
            raise BaoStockDataError("BaoStock returned no profit/share observations")
        raw = _prepare_raw(history, pd.concat(fundamentals, ignore_index=True))
        panel = prepare_ivol_panel(
            raw,
            minimum_daily_observations=config.minimum_daily_observations,
        )
        raw.to_parquet(raw_path, index=False)
        panel.to_parquet(panel_path, index=False)
        manifest = {
            "provider": "BaoStock",
            "pipeline_version": _PIPELINE_VERSION,
            "config_id": identifier,
            "requested_codes": list(config.codes),
            "start_date": config.start_date.isoformat(),
            "end_date": config.end_date.isoformat(),
            "adjust_flag": self.settings.adjust_flag,
            "raw_rows": len(raw),
            "panel_rows": len(panel),
            "created_at_utc": datetime.now(UTC).isoformat(),
            "point_in_time_policy": (
                "Quarterly totalShare is joined only on or after its pubDate."
            ),
            "methodology": (
                "Monthly IVOL is residual volatility from a daily single-index model; "
                "size is log(close * most recently published totalShare); bm is "
                "inverse pbMRQ; momentum is months t-12 through t-2."
            ),
            "limitations": [
                "Selected-code MVP does not eliminate survivorship bias.",
                "Single-index IVOL is not a Fama-French residual-volatility estimate.",
                "Provider data and adjustment conventions require independent review.",
            ],
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return BaoStockBuildResult(
            raw_path=raw_path,
            panel_path=panel_path,
            manifest_path=manifest_path,
            raw_rows=len(raw),
            panel_rows=len(panel),
            cache_hit=False,
        )
