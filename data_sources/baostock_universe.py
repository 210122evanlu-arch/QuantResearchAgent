"""Historical month-end A-share universe snapshots from BaoStock."""

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
from data_sources.baostock import BaoStockDataError, BaoStockResult, _result_frame

_PIPELINE_VERSION = 3
_A_SHARE_PATTERN = re.compile(
    r"^(?:sh\.(?:60[0135]|68[89])\d{3}|sz\.(?:00[0-3]|30[01])\d{3}|bj\.\d{6})$",
    re.IGNORECASE,
)


class BaoStockUniverseAPI(Protocol):
    def login(self) -> BaoStockResult: ...

    def logout(self) -> BaoStockResult: ...

    def query_trade_dates(self, **kwargs: Any) -> BaoStockResult: ...

    def query_all_stock(self, **kwargs: Any) -> BaoStockResult: ...


@dataclass(frozen=True)
class BaoStockUniverseConfig:
    start_date: date
    end_date: date
    include_beijing: bool = True
    refresh: bool = False

    def __post_init__(self) -> None:
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")


@dataclass(frozen=True)
class BaoStockUniverseResult:
    universe_path: Path
    manifest_path: Path
    rows: int
    unique_securities: int
    monthly_snapshots: int
    cache_hit: bool


def _identifier(config: BaoStockUniverseConfig) -> str:
    payload = {
        "start": config.start_date.isoformat(),
        "end": config.end_date.isoformat(),
        "include_beijing": config.include_beijing,
        "pipeline_version": _PIPELINE_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


def _is_supported_a_share(code: str, include_beijing: bool) -> bool:
    if not _A_SHARE_PATTERN.fullmatch(code):
        return False
    return include_beijing or not code.casefold().startswith("bj.")


class BaoStockHistoricalUniverseBuilder:
    """Build cached month-end security snapshots, including later-delisted names."""

    def __init__(
        self,
        settings: BaoStockSettings,
        api: BaoStockUniverseAPI | None = None,
    ) -> None:
        self.settings = settings
        self.api = api or bs

    def _login(self) -> None:
        result = self.api.login()
        if result.error_code != "0":
            raise BaoStockDataError(
                f"BaoStock login failed [{result.error_code}]: {result.error_msg}"
            )

    def _query(
        self,
        call: Callable[[], BaoStockResult],
        endpoint: str,
        max_attempts: int = 4,
    ) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return _result_frame(call(), endpoint)
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

    def build(self, config: BaoStockUniverseConfig) -> BaoStockUniverseResult:
        directory = self.settings.cache_directory / "universe"
        directory.mkdir(parents=True, exist_ok=True)
        identifier = _identifier(config)
        universe_path = directory / f"a_share_month_end_{identifier}.parquet"
        manifest_path = directory / f"a_share_month_end_{identifier}.json"
        if universe_path.exists() and manifest_path.exists() and not config.refresh:
            frame = pd.read_parquet(universe_path)
            return BaoStockUniverseResult(
                universe_path=universe_path,
                manifest_path=manifest_path,
                rows=len(frame),
                unique_securities=frame["stock_id"].nunique(),
                monthly_snapshots=frame["date"].nunique(),
                cache_hit=True,
            )

        self._login()
        try:
            calendar = self._query(
                lambda: self.api.query_trade_dates(
                    start_date=config.start_date.isoformat(),
                    end_date=config.end_date.isoformat(),
                ),
                "query_trade_dates",
            )
            required_calendar = {"calendar_date", "is_trading_day"}
            if not required_calendar.issubset(calendar.columns):
                raise BaoStockDataError(
                    "BaoStock trading calendar fields are incomplete"
                )
            calendar["date"] = pd.to_datetime(
                calendar["calendar_date"], errors="coerce"
            )
            trading = calendar.loc[calendar["is_trading_day"].astype(str) == "1"]
            month_ends = (
                trading.groupby(trading["date"].dt.to_period("M"))["date"]
                .max()
                .sort_values()
            )
            snapshots: list[pd.DataFrame] = []
            for snapshot_date in month_ends:
                stocks = self._query(
                    partial(
                        self.api.query_all_stock,
                        day=snapshot_date.strftime("%Y-%m-%d"),
                    ),
                    "query_all_stock",
                )
                required = {"code", "tradeStatus", "code_name"}
                if not required.issubset(stocks.columns):
                    raise BaoStockDataError("BaoStock universe fields are incomplete")
                stocks = stocks.loc[
                    stocks["code"]
                    .astype(str)
                    .map(
                        lambda code: _is_supported_a_share(code, config.include_beijing)
                    )
                ].copy()
                stocks["date"] = snapshot_date
                stocks = stocks.rename(
                    columns={
                        "code": "stock_id",
                        "tradeStatus": "trade_status",
                        "code_name": "security_name",
                    }
                )
                stocks["special_treatment"] = stocks["security_name"].str.contains(
                    r"(?:ST|PT)", case=False, regex=True, na=False
                )
                snapshots.append(
                    stocks[
                        [
                            "date",
                            "stock_id",
                            "security_name",
                            "trade_status",
                            "special_treatment",
                        ]
                    ]
                )
        finally:
            self.api.logout()

        if not snapshots:
            raise BaoStockDataError("No historical A-share snapshots were returned")
        universe = pd.concat(snapshots, ignore_index=True).sort_values(
            ["date", "stock_id"]
        )
        universe.to_parquet(universe_path, index=False)
        observed_exchanges = sorted(
            universe["stock_id"].str.split(".").str[0].str.lower().unique().tolist()
        )
        limitations = [
            "Industry exclusions require a separate point-in-time source.",
            "First appearance inside the requested window is not an IPO date.",
            "Provider history and delisting coverage require independent audit.",
        ]
        if config.include_beijing and "bj" not in observed_exchanges:
            limitations.append(
                "Beijing A-shares were requested but were absent from BaoStock snapshots."
            )
        manifest = {
            "provider": "BaoStock",
            "pipeline_version": _PIPELINE_VERSION,
            "start_date": config.start_date.isoformat(),
            "end_date": config.end_date.isoformat(),
            "include_beijing": config.include_beijing,
            "observed_exchanges": observed_exchanges,
            "rows": len(universe),
            "unique_securities": universe["stock_id"].nunique(),
            "monthly_snapshots": universe["date"].nunique(),
            "created_at_utc": datetime.now(UTC).isoformat(),
            "limitations": limitations,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return BaoStockUniverseResult(
            universe_path=universe_path,
            manifest_path=manifest_path,
            rows=len(universe),
            unique_securities=universe["stock_id"].nunique(),
            monthly_snapshots=universe["date"].nunique(),
            cache_hit=False,
        )
