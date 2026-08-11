"""Tushare Pro adapter and deterministic IVOL panel preparation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
import pandas as pd
import tushare as ts

from config import TushareSettings

_PIPELINE_VERSION = 2


class TushareDataError(RuntimeError):
    """Raised when Tushare data cannot be acquired or prepared safely."""


class TushareAPI(Protocol):
    def daily(self, **kwargs: Any) -> pd.DataFrame: ...

    def daily_basic(self, **kwargs: Any) -> pd.DataFrame: ...


@dataclass(frozen=True)
class TushareBuildConfig:
    ts_codes: tuple[str, ...]
    start_date: date
    end_date: date
    minimum_daily_observations: int = 10
    refresh: bool = False

    def __post_init__(self) -> None:
        if not self.ts_codes:
            raise ValueError("At least one Tushare stock code is required")
        if len(self.ts_codes) > 50:
            raise ValueError("MVP downloads are limited to 50 selected stock codes")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        if self.minimum_daily_observations < 5:
            raise ValueError("minimum_daily_observations must be at least 5")
        invalid = [code for code in self.ts_codes if "." not in code]
        if invalid:
            raise ValueError(
                "Tushare codes require an exchange suffix: " + ", ".join(invalid)
            )


@dataclass(frozen=True)
class TushareBuildResult:
    raw_path: Path
    panel_path: Path
    manifest_path: Path
    raw_rows: int
    panel_rows: int
    cache_hit: bool


def _config_id(config: TushareBuildConfig) -> str:
    payload = {
        "codes": sorted(config.ts_codes),
        "start": config.start_date.isoformat(),
        "end": config.end_date.isoformat(),
        "minimum_daily_observations": config.minimum_daily_observations,
        "pipeline_version": _PIPELINE_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


def _required_columns(frame: pd.DataFrame, required: set[str], endpoint: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise TushareDataError(
            f"Tushare endpoint {endpoint!r} omitted fields: {', '.join(missing)}"
        )


def prepare_ivol_panel(
    raw: pd.DataFrame,
    *,
    minimum_daily_observations: int = 10,
) -> pd.DataFrame:
    """Build a monthly single-index IVOL panel from downloaded daily data."""
    required = {"ts_code", "trade_date", "pct_chg", "total_mv", "pb"}
    _required_columns(raw, required, "merged daily/daily_basic")
    frame = raw.copy()
    frame["date"] = pd.to_datetime(
        frame["trade_date"], format="%Y%m%d", errors="coerce"
    )
    if frame["date"].isna().any():
        raise TushareDataError("Tushare returned unparseable trade_date values")
    frame["return"] = pd.to_numeric(frame["pct_chg"], errors="coerce") / 100.0
    frame["total_mv"] = pd.to_numeric(frame["total_mv"], errors="coerce")
    frame["pb"] = pd.to_numeric(frame["pb"], errors="coerce")
    if "turnover_rate" in frame.columns:
        frame["turnover_rate"] = pd.to_numeric(frame["turnover_rate"], errors="coerce")
    frame["market_return"] = frame.groupby("date")["return"].transform("mean")
    frame["month"] = frame["date"].dt.to_period("M")
    frame = frame.sort_values(["ts_code", "date"])

    rows: list[dict[str, Any]] = []
    for (stock_id, _month), group in frame.groupby(["ts_code", "month"]):
        regression = group[["return", "market_return"]].dropna()
        if len(regression) < minimum_daily_observations:
            continue
        market = regression["market_return"].to_numpy(dtype=float)
        design = np.column_stack([np.ones(len(market)), market])
        stock_return = regression["return"].to_numpy(dtype=float)
        coefficients = np.linalg.lstsq(design, stock_return, rcond=None)[0]
        residuals = stock_return - design @ coefficients
        latest = group.iloc[-1]
        total_mv = float(latest["total_mv"])
        pb = float(latest["pb"])
        row = {
            "stock_id": str(stock_id),
            "date": group["date"].max(),
            "monthly_return": float(np.prod(1.0 + stock_return) - 1.0),
            "IVOL": float(np.std(residuals, ddof=1)),
            "size": float(np.log(total_mv)) if total_mv > 0 else np.nan,
            "bm": 1.0 / pb if pb > 0 else np.nan,
            "daily_observations": len(regression),
        }
        if "turnover_rate" in group.columns:
            row["turnover"] = float(group["turnover_rate"].sum(min_count=1))
        rows.append(row)

    panel = pd.DataFrame(rows)
    if panel.empty:
        raise TushareDataError(
            "No stock-month meets the minimum daily-observation requirement"
        )
    panel = panel.sort_values(["stock_id", "date"]).reset_index(drop=True)
    grouped = panel.groupby("stock_id", group_keys=False)
    panel["target_date"] = grouped["date"].shift(-1)
    panel["future_return"] = grouped["monthly_return"].shift(-1)
    panel["momentum"] = grouped["monthly_return"].transform(
        lambda values: (
            (1.0 + values).shift(2).rolling(11, min_periods=11).apply(np.prod) - 1.0
        )
    )
    model_columns = [
        "target_date",
        "future_return",
        "IVOL",
        "size",
        "bm",
        "momentum",
    ]
    return panel.dropna(subset=model_columns).reset_index(drop=True)


class TushareIVOLDataBuilder:
    """Download selected-stock histories and cache a research-ready panel."""

    def __init__(
        self,
        settings: TushareSettings,
        api: TushareAPI | None = None,
    ) -> None:
        self.settings = settings
        self.api = api or cast(TushareAPI, ts.pro_api(settings.token))

    def build(self, config: TushareBuildConfig) -> TushareBuildResult:
        cache_directory = self.settings.cache_directory
        cache_directory.mkdir(parents=True, exist_ok=True)
        identifier = _config_id(config)
        raw_path = cache_directory / f"ivol_daily_{identifier}.parquet"
        panel_path = cache_directory / f"ivol_panel_{identifier}.parquet"
        manifest_path = cache_directory / f"ivol_manifest_{identifier}.json"
        if panel_path.exists() and raw_path.exists() and not config.refresh:
            return TushareBuildResult(
                raw_path=raw_path,
                panel_path=panel_path,
                manifest_path=manifest_path,
                raw_rows=len(pd.read_parquet(raw_path)),
                panel_rows=len(pd.read_parquet(panel_path)),
                cache_hit=True,
            )

        frames: list[pd.DataFrame] = []
        start = config.start_date.strftime("%Y%m%d")
        end = config.end_date.strftime("%Y%m%d")
        for code in config.ts_codes:
            try:
                daily = self.api.daily(
                    ts_code=code,
                    start_date=start,
                    end_date=end,
                    fields="ts_code,trade_date,close,pre_close,pct_chg,vol,amount",
                )
                basic = self.api.daily_basic(
                    ts_code=code,
                    start_date=start,
                    end_date=end,
                    fields="ts_code,trade_date,total_mv,pb,turnover_rate",
                )
            except Exception as exc:
                raise TushareDataError(
                    f"Tushare request failed for {code}; verify token, points, and quota"
                ) from exc
            _required_columns(daily, {"ts_code", "trade_date", "pct_chg"}, "daily")
            _required_columns(
                basic,
                {"ts_code", "trade_date", "total_mv", "pb"},
                "daily_basic",
            )
            frames.append(daily.merge(basic, on=["ts_code", "trade_date"], how="inner"))

        raw = pd.concat(frames, ignore_index=True)
        if raw.empty:
            raise TushareDataError("Tushare returned no matched daily observations")
        panel = prepare_ivol_panel(
            raw,
            minimum_daily_observations=config.minimum_daily_observations,
        )
        if panel.empty:
            raise TushareDataError(
                "Prepared panel is empty; use a longer period for momentum construction"
            )
        raw.to_parquet(raw_path, index=False)
        panel.to_parquet(panel_path, index=False)
        manifest = {
            "provider": "Tushare Pro",
            "pipeline_version": _PIPELINE_VERSION,
            "config_id": identifier,
            "requested_codes": list(config.ts_codes),
            "start_date": config.start_date.isoformat(),
            "end_date": config.end_date.isoformat(),
            "raw_rows": len(raw),
            "panel_rows": len(panel),
            "created_at_utc": datetime.now(UTC).isoformat(),
            "methodology": (
                "Monthly IVOL is residual volatility from a daily single-index model; "
                "momentum is months t-12 through t-2; bm is inverse price-to-book."
            ),
            "limitations": [
                "Selected-code MVP does not eliminate survivorship bias.",
                "Single-index IVOL is not a Fama-French residual-volatility estimate.",
            ],
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return TushareBuildResult(
            raw_path=raw_path,
            panel_path=panel_path,
            manifest_path=manifest_path,
            raw_rows=len(raw),
            panel_rows=len(panel),
            cache_hit=False,
        )
