"""Resumable full-universe BaoStock daily-return downloader."""

from __future__ import annotations

import atexit
import json
import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import baostock as bs
import pandas as pd
from baostock.common import context

LOGGER = logging.getLogger(__name__)
DAILY_FIELDS = (
    "date",
    "code",
    "close",
    "preclose",
    "pctChg",
    "tradestatus",
    "isST",
)
MONTHLY_FIELDS = ("date", "code", "close", "pctChg")


class BaoStockReturnDataError(RuntimeError):
    """Raised when the daily-return cache cannot be built safely."""


class _PagedResult(Protocol):
    error_code: str
    error_msg: str
    fields: list[str]
    data: list[list[str]]
    cur_row_num: int

    def next(self) -> bool: ...


@dataclass(frozen=True)
class BaoStockReturnConfig:
    codes: tuple[str, ...]
    start_date: date
    end_date: date
    output_directory: Path
    workers: int = 4
    adjust_flag: str = "3"
    frequency: Literal["d", "m"] = "m"
    refresh: bool = False
    batch_size: int = 200
    batch_pause_seconds: float = 3.0

    def __post_init__(self) -> None:
        if not self.codes:
            raise ValueError("At least one BaoStock code is required")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        if not 1 <= self.workers <= 8:
            raise ValueError("workers must be between 1 and 8")
        if self.adjust_flag not in {"1", "2", "3"}:
            raise ValueError("adjust_flag must be 1, 2, or 3")
        if self.batch_size < self.workers:
            raise ValueError("batch_size must be at least the worker count")
        if self.batch_pause_seconds < 0:
            raise ValueError("batch_pause_seconds must be nonnegative")


@dataclass(frozen=True)
class BaoStockReturnResult:
    stock_directory: Path
    manifest_path: Path
    requested_codes: int
    completed_codes: int
    rows: int
    cache_hits: int
    empty_codes: int
    failed_codes: int


def stock_cache_path(directory: Path, code: str) -> Path:
    return directory / f"{code.casefold().replace('.', '_')}.parquet"


def _paged_frame(result: _PagedResult) -> pd.DataFrame:
    """Collect result pages without BaoStock's removed DataFrame.append call."""
    if result.error_code != "0":
        raise BaoStockReturnDataError(
            f"BaoStock query failed [{result.error_code}]: {result.error_msg}"
        )
    pages: list[pd.DataFrame] = []
    if result.data:
        pages.append(pd.DataFrame(result.data, columns=result.fields))
    while result.data:
        result.cur_row_num = len(result.data)
        if not result.next():
            break
        pages.append(pd.DataFrame(result.data, columns=result.fields))
    if not pages:
        return pd.DataFrame(columns=result.fields)
    return pd.concat(pages, ignore_index=True)


def _normalize_history(
    frame: pd.DataFrame, code: str, frequency: Literal["d", "m"]
) -> pd.DataFrame:
    fields = DAILY_FIELDS if frequency == "d" else MONTHLY_FIELDS
    required = set(fields)
    missing = sorted(required - set(frame.columns))
    if missing:
        raise BaoStockReturnDataError(
            f"BaoStock history for {code} is missing: " + ", ".join(missing)
        )
    history = frame[list(fields)].copy()
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history["close"] = pd.to_numeric(history["close"], errors="coerce")
    if "preclose" in history:
        history["preclose"] = pd.to_numeric(history["preclose"], errors="coerce")
    else:
        history["preclose"] = pd.NA
    history["daily_return"] = pd.to_numeric(history["pctChg"], errors="coerce") / 100.0
    history["trade_status"] = (
        history["tradestatus"].astype(str) if "tradestatus" in history else "1"
    )
    history["special_treatment"] = (
        history["isST"].astype(str).eq("1") if "isST" in history else False
    )
    history["stock_id"] = code.casefold()
    history = history.dropna(subset=["date"]).sort_values("date")
    if history["date"].duplicated().any():
        raise BaoStockReturnDataError(f"BaoStock returned duplicate dates for {code}")
    return history[
        [
            "date",
            "stock_id",
            "close",
            "preclose",
            "daily_return",
            "trade_status",
            "special_treatment",
        ]
    ].reset_index(drop=True)


def _login() -> None:
    last_error = "unknown error"
    for attempt in range(1, 5):
        result = bs.login()
        if result.error_code == "0":
            default_socket = getattr(context, "default_socket", None)
            if default_socket is not None:
                default_socket.settimeout(45)
            atexit.register(bs.logout)
            return
        last_error = f"[{result.error_code}]: {result.error_msg}"
        time.sleep(attempt)
    raise BaoStockReturnDataError(f"BaoStock login failed {last_error}")


def _fetch_one(
    payload: tuple[str, str, str, str, Literal["d", "m"], str],
) -> dict[str, Any]:
    code, start_date, end_date, adjust_flag, frequency, output_directory = payload
    output_path = stock_cache_path(Path(output_directory), code)
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            fields = DAILY_FIELDS if frequency == "d" else MONTHLY_FIELDS
            result = bs.query_history_k_data_plus(
                code,
                ",".join(fields),
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag=adjust_flag,
            )
            history = _normalize_history(_paged_frame(result), code, frequency)
            history.to_parquet(output_path, index=False)
            return {
                "code": code,
                "rows": len(history),
                "empty": history.empty,
                "path": str(output_path),
            }
        except Exception as exc:
            last_error = exc
            if attempt == 4:
                break
            try:
                bs.logout()
            except Exception:
                pass
            time.sleep(attempt)
            login = bs.login()
            if login.error_code != "0":
                last_error = BaoStockReturnDataError(login.error_msg)
            default_socket = getattr(context, "default_socket", None)
            if default_socket is not None:
                default_socket.settimeout(45)
    raise BaoStockReturnDataError(f"Failed to download {code}") from last_error


def _cached_summary(path: Path, code: str) -> dict[str, Any]:
    frame = pd.read_parquet(path, columns=["date"])
    return {"code": code, "rows": len(frame), "empty": frame.empty, "path": str(path)}


def _write_manifest(
    path: Path,
    config: BaoStockReturnConfig,
    records: list[dict[str, Any]],
    cache_hits: int,
    failed_codes: list[str] | None = None,
) -> None:
    failed_codes = failed_codes or []
    payload = {
        "provider": "BaoStock",
        "source_field": "pctChg",
        "frequency": config.frequency,
        "adjust_flag": config.adjust_flag,
        "start_date": config.start_date.isoformat(),
        "end_date": config.end_date.isoformat(),
        "requested_codes": len(config.codes),
        "completed_codes": len(records),
        "rows": sum(int(record["rows"]) for record in records),
        "empty_codes": sum(bool(record["empty"]) for record in records),
        "cache_hits": cache_hits,
        "failed_codes": failed_codes,
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "status": "complete" if len(records) == len(config.codes) else "in_progress",
        "limitations": [
            "BaoStock provider history and delisting coverage require independent audit.",
            "Historical industry classifications are not included.",
        ],
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def build_baostock_return_cache(
    config: BaoStockReturnConfig,
) -> BaoStockReturnResult:
    """Download one independent Parquet per stock with resumable progress."""
    stock_directory = config.output_directory / "stocks"
    stock_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = config.output_directory / "manifest.json"
    records: list[dict[str, Any]] = []
    pending: list[str] = []
    failed_codes: list[str] = []
    cache_hits = 0
    for code in sorted(set(config.codes)):
        path = stock_cache_path(stock_directory, code)
        if path.exists() and not config.refresh:
            records.append(_cached_summary(path, code))
            cache_hits += 1
        else:
            pending.append(code)
    _write_manifest(manifest_path, config, records, cache_hits)

    payloads = [
        (
            code,
            config.start_date.isoformat(),
            config.end_date.isoformat(),
            config.adjust_flag,
            config.frequency,
            str(stock_directory),
        )
        for code in pending
    ]
    for batch_start in range(0, len(payloads), config.batch_size):
        batch = payloads[batch_start : batch_start + config.batch_size]
        with ProcessPoolExecutor(
            max_workers=config.workers, initializer=_login
        ) as executor:
            futures = {
                executor.submit(_fetch_one, payload): payload[0] for payload in batch
            }
            for future in as_completed(futures):
                code = futures[future]
                try:
                    records.append(future.result())
                except Exception as exc:
                    failed_codes.append(code)
                    LOGGER.error(
                        "BaoStock return download failed for %s: %s", code, exc
                    )
        _write_manifest(manifest_path, config, records, cache_hits, failed_codes)
        LOGGER.info(
            "BaoStock returns: %s/%s codes complete; batch failures=%s",
            len(records),
            len(config.codes),
            len(failed_codes),
        )
        if batch_start + config.batch_size < len(payloads):
            time.sleep(config.batch_pause_seconds)
    records.sort(key=lambda record: str(record["code"]))
    _write_manifest(manifest_path, config, records, cache_hits, failed_codes)
    return BaoStockReturnResult(
        stock_directory=stock_directory,
        manifest_path=manifest_path,
        requested_codes=len(config.codes),
        completed_codes=len(records),
        rows=sum(int(record["rows"]) for record in records),
        cache_hits=cache_hits,
        empty_codes=sum(bool(record["empty"]) for record in records),
        failed_codes=len(failed_codes),
    )


def load_baostock_monthly_returns(stock_directory: Path) -> pd.DataFrame:
    """Load and validate per-stock monthly pctChg cache files."""
    paths = sorted(stock_directory.glob("*.parquet"))
    if not paths:
        raise BaoStockReturnDataError(
            f"No BaoStock return cache files found in {stock_directory}"
        )
    frames = [
        pd.read_parquet(path, columns=["date", "stock_id", "daily_return"])
        for path in paths
    ]
    returns = pd.concat(frames, ignore_index=True)
    returns["date"] = pd.to_datetime(returns["date"], errors="coerce")
    returns["daily_return"] = pd.to_numeric(returns["daily_return"], errors="coerce")
    returns["stock_id"] = returns["stock_id"].astype(str).str.rsplit(".").str[-1]
    returns["month"] = returns["date"].dt.to_period("M")
    returns = returns.dropna(subset=["date", "daily_return"])
    if returns.duplicated(["stock_id", "month"]).any():
        raise BaoStockReturnDataError(
            "BaoStock monthly cache contains duplicate stock-month rows"
        )
    return returns[["stock_id", "month", "date", "daily_return"]]


def align_baostock_future_returns(
    ivol_panel: pd.DataFrame,
    monthly_returns: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Replace the target with BaoStock's next-calendar-month unadjusted return."""
    panel = ivol_panel.copy()
    panel["month"] = pd.PeriodIndex(panel["month"], freq="M")
    target = monthly_returns.rename(
        columns={
            "month": "target_month_baostock",
            "date": "target_date_baostock",
            "daily_return": "future_return_baostock",
        }
    ).copy()
    target["month"] = target["target_month_baostock"] - 1
    merged = panel.merge(
        target[
            [
                "stock_id",
                "month",
                "target_month_baostock",
                "target_date_baostock",
                "future_return_baostock",
            ]
        ],
        on=["stock_id", "month"],
        how="left",
        validate="one_to_one",
    )
    comparable = merged[["future_return", "future_return_baostock"]].dropna()
    correlation = (
        comparable["future_return"]
        .astype(float)
        .corr(comparable["future_return_baostock"].astype(float))
        if len(comparable) > 1
        else None
    )
    audit = {
        "ivol_rows_before_target_join": len(panel),
        "baostock_target_matches": int(merged["future_return_baostock"].notna().sum()),
        "baostock_target_missing": int(merged["future_return_baostock"].isna().sum()),
        "akshare_baostock_comparable_rows": len(comparable),
        "akshare_baostock_return_correlation": (
            float(correlation) if correlation is not None else None
        ),
        "akshare_baostock_median_absolute_difference": (
            float(
                (comparable["future_return"] - comparable["future_return_baostock"])
                .abs()
                .median()
            )
            if len(comparable)
            else None
        ),
    }
    merged["future_return_akshare"] = merged["future_return"]
    merged["future_return"] = merged["future_return_baostock"]
    merged["target_month"] = merged["target_month_baostock"]
    merged["target_date"] = merged["target_date_baostock"]
    merged["target_is_next_calendar_month"] = merged["future_return"].notna()
    merged["target_return_provider"] = "BaoStock pctChg, unadjusted monthly"
    return merged, audit
