"""Auditable China government-bond yield proxy for daily risk-free returns."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Literal, Protocol, cast

import pandas as pd
import requests

CHINABOND_HISTORY_URL = "https://yield.chinabond.com.cn/cbweb-pbc-web/pbc/historyQuery"
MATURITIES = ("3月", "6月", "1年")


class RiskFreeDataError(ValueError):
    """Raised when a risk-free proxy cannot satisfy the data contract."""


class _Response(Protocol):
    text: str

    def raise_for_status(self) -> None: ...


class _Session(Protocol):
    def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        headers: dict[str, str],
        timeout: float,
    ) -> _Response: ...


@dataclass(frozen=True)
class ChinaBondRiskFreeConfig:
    start_date: date
    end_date: date
    output_path: Path
    maturity: Literal["3月", "6月", "1年"] = "3月"
    annualization_days: int = 252
    curve_name: str = "中债国债收益率曲线"
    timeout_seconds: float = 45.0
    pause_seconds: float = 0.5
    refresh: bool = False

    def __post_init__(self) -> None:
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        if self.maturity not in MATURITIES:
            raise ValueError(f"maturity must be one of {MATURITIES}")
        if self.annualization_days <= 0:
            raise ValueError("annualization_days must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.pause_seconds < 0:
            raise ValueError("pause_seconds must be nonnegative")


@dataclass(frozen=True)
class ChinaBondRiskFreeResult:
    data_path: Path
    manifest_path: Path
    rows: int
    start_date: date
    end_date: date
    cache_hit: bool


def _date_chunks(start: date, end: date) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=364), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _parse_history_html(html: str, *, curve_name: str, maturity: str) -> pd.DataFrame:
    try:
        tables = pd.read_html(StringIO(html.replace("&nbsp", "")), header=0)
    except ValueError as exc:
        raise RiskFreeDataError("ChinaBond response contains no tables") from exc
    required = {"曲线名称", "日期", maturity}
    candidates = [table for table in tables if required.issubset(table.columns)]
    if not candidates:
        raise RiskFreeDataError(
            "ChinaBond response is missing required yield-curve columns"
        )
    frame = candidates[0]
    frame = frame.loc[frame["曲线名称"].astype(str).eq(curve_name)].copy()
    frame["date"] = pd.to_datetime(frame["日期"], errors="coerce")
    frame["annual_yield_percent"] = pd.to_numeric(frame[maturity], errors="coerce")
    frame = frame.dropna(subset=["date", "annual_yield_percent"])
    if frame.empty:
        raise RiskFreeDataError(
            f"ChinaBond response has no {curve_name!r} observations for {maturity}"
        )
    if not frame["annual_yield_percent"].between(-10, 50).all():
        raise RiskFreeDataError("ChinaBond annual yields fall outside safety bounds")
    return frame[["date", "annual_yield_percent"]]


def _fetch_chunk(
    session: _Session,
    start: date,
    end: date,
    config: ChinaBondRiskFreeConfig,
) -> pd.DataFrame:
    params = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "gjqx": "0",
        "qxId": "ycqx",
        "locale": "cn_ZH",
    }
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = session.get(
                CHINABOND_HISTORY_URL,
                params=params,
                headers={"User-Agent": "Mozilla/5.0 QuantResearchAgent/1.0"},
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
            return _parse_history_html(
                response.text,
                curve_name=config.curve_name,
                maturity=config.maturity,
            )
        except (requests.RequestException, RiskFreeDataError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt)
    raise RiskFreeDataError(
        f"ChinaBond download failed for {start} through {end}"
    ) from last_error


def _normalize_download(
    frames: list[pd.DataFrame], config: ChinaBondRiskFreeConfig
) -> pd.DataFrame:
    if not frames:
        raise RiskFreeDataError("ChinaBond download returned no data")
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("date").drop_duplicates("date", keep="last")
    combined = combined.loc[
        combined["date"].between(
            pd.Timestamp(config.start_date), pd.Timestamp(config.end_date)
        )
    ].copy()
    if combined.empty:
        raise RiskFreeDataError("ChinaBond data does not cover the requested period")
    annual_decimal = combined["annual_yield_percent"] / 100.0
    combined["RF"] = (1.0 + annual_decimal).pow(1.0 / config.annualization_days) - 1.0
    combined["source"] = "ChinaBond government yield curve"
    combined["curve_name"] = config.curve_name
    combined["maturity"] = config.maturity
    combined["annualization_days"] = config.annualization_days
    return combined.reset_index(drop=True)


def _manifest_payload(
    frame: pd.DataFrame, config: ChinaBondRiskFreeConfig
) -> dict[str, Any]:
    return {
        "provider": "ChinaBond",
        "source_url": CHINABOND_HISTORY_URL,
        "curve_name": config.curve_name,
        "maturity": config.maturity,
        "annualization_days": config.annualization_days,
        "conversion": "RF=(1+annual_yield_percent/100)^(1/annualization_days)-1",
        "requested_start_date": config.start_date.isoformat(),
        "requested_end_date": config.end_date.isoformat(),
        "observed_start_date": frame["date"].min().date().isoformat(),
        "observed_end_date": frame["date"].max().date().isoformat(),
        "rows": len(frame),
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "limitations": [
            "This is a transparent three-month government-yield proxy, not the original CSMAR RF series.",
            "The annual yield is converted to a per-trading-day effective return using the configured annualization day count.",
        ],
    }


def download_chinabond_risk_free(
    config: ChinaBondRiskFreeConfig,
    *,
    session: _Session | None = None,
) -> ChinaBondRiskFreeResult:
    """Download a resumable local risk-free proxy and adjacent audit manifest."""
    manifest_path = config.output_path.with_suffix(".manifest.json")
    if config.output_path.exists() and manifest_path.exists() and not config.refresh:
        cached = load_risk_free_proxy(config.output_path)
        return ChinaBondRiskFreeResult(
            data_path=config.output_path,
            manifest_path=manifest_path,
            rows=len(cached),
            start_date=cached["date"].min().date(),
            end_date=cached["date"].max().date(),
            cache_hit=True,
        )
    active_session = session or cast(_Session, requests.Session())
    frames: list[pd.DataFrame] = []
    chunks = _date_chunks(config.start_date, config.end_date)
    for index, (start, end) in enumerate(chunks):
        frames.append(_fetch_chunk(active_session, start, end, config))
        if index + 1 < len(chunks):
            time.sleep(config.pause_seconds)
    frame = _normalize_download(frames, config)
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(config.output_path, index=False)
    manifest_path.write_text(
        json.dumps(_manifest_payload(frame, config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ChinaBondRiskFreeResult(
        data_path=config.output_path,
        manifest_path=manifest_path,
        rows=len(frame),
        start_date=frame["date"].min().date(),
        end_date=frame["date"].max().date(),
        cache_hit=False,
    )


def load_risk_free_proxy(path: Path) -> pd.DataFrame:
    """Load and validate a daily risk-free proxy file."""
    if not path.exists():
        raise RiskFreeDataError(f"Risk-free file does not exist: {path}")
    frame = pd.read_parquet(path).copy()
    required = {"date", "RF"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RiskFreeDataError("Risk-free data is missing: " + ", ".join(missing))
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["RF"] = pd.to_numeric(frame["RF"], errors="coerce")
    if frame[["date", "RF"]].isna().any().any():
        raise RiskFreeDataError("Risk-free data contains invalid dates or values")
    if frame["date"].duplicated().any():
        raise RiskFreeDataError("Risk-free data contains duplicate dates")
    if not frame["RF"].between(-0.01, 0.01).all():
        raise RiskFreeDataError("Daily risk-free returns fall outside safety bounds")
    return frame.sort_values("date").reset_index(drop=True)


def align_risk_free_to_dates(
    dates: pd.Series,
    risk_free: pd.DataFrame,
    *,
    max_staleness_days: int = 7,
) -> pd.DataFrame:
    """Backward-align yields to trading dates without using future information."""
    if max_staleness_days < 0:
        raise ValueError("max_staleness_days must be nonnegative")
    target = pd.DataFrame({"date": pd.to_datetime(dates, errors="coerce")})
    if target["date"].isna().any():
        raise RiskFreeDataError("Target dates contain invalid values")
    target = target.drop_duplicates().sort_values("date")
    source = risk_free[["date", "RF"]].rename(columns={"date": "risk_free_source_date"})
    aligned = pd.merge_asof(
        target,
        source.sort_values("risk_free_source_date"),
        left_on="date",
        right_on="risk_free_source_date",
        direction="backward",
        tolerance=pd.Timedelta(days=max_staleness_days),
    )
    if aligned["RF"].isna().any():
        missing = int(aligned["RF"].isna().sum())
        raise RiskFreeDataError(
            f"Risk-free proxy fails to cover {missing} target dates within "
            f"{max_staleness_days} days"
        )
    aligned["risk_free_staleness_days"] = (
        aligned["date"] - aligned["risk_free_source_date"]
    ).dt.days
    return aligned
