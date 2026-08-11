"""Point-in-time BaoStock industry snapshots for thesis sample filtering."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import baostock as bs
import pandas as pd

from data_sources.baostock_returns import _login, _paged_frame


class BaoStockIndustryError(ValueError):
    """Raised when industry snapshots cannot satisfy the data contract."""


@dataclass(frozen=True)
class BaoStockIndustryConfig:
    snapshot_dates: tuple[date, ...]
    output_directory: Path
    refresh: bool = False
    pause_seconds: float = 1.0

    def __post_init__(self) -> None:
        if not self.snapshot_dates:
            raise ValueError("At least one industry snapshot date is required")
        if self.pause_seconds < 0:
            raise ValueError("pause_seconds must be nonnegative")


@dataclass(frozen=True)
class BaoStockIndustryResult:
    snapshot_directory: Path
    manifest_path: Path
    requested_snapshots: int
    completed_snapshots: int
    rows: int
    cache_hits: int


def industry_snapshot_path(directory: Path, snapshot_date: date) -> Path:
    return directory / f"industry_{snapshot_date.isoformat()}.parquet"


def _repair_baostock_text(value: object) -> str:
    if value is None or value is pd.NA or value is pd.NaT:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    try:
        repaired = text.encode("latin1").decode("gb18030")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    original_cjk = sum("\u4e00" <= character <= "\u9fff" for character in text)
    repaired_cjk = sum("\u4e00" <= character <= "\u9fff" for character in repaired)
    return repaired if repaired_cjk > original_cjk else text


def _add_industry_flags(frame: pd.DataFrame) -> pd.DataFrame:
    flagged = frame.copy()
    industry = flagged["industry"]
    flagged["financial_industry"] = industry.str.match(
        r"^J6[6-9]"
    ) | industry.str.contains("金融保险业|银行业|证券业|保险业", regex=True)
    flagged["real_estate_industry"] = industry.str.startswith(
        "K70"
    ) | industry.str.contains("房地产业", regex=False)
    flagged["excluded_industry"] = (
        flagged["financial_industry"] | flagged["real_estate_industry"]
    )
    return flagged


def _normalize_industry_snapshot(
    frame: pd.DataFrame, snapshot_date: date
) -> pd.DataFrame:
    required = {
        "updateDate",
        "code",
        "code_name",
        "industry",
        "industryClassification",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise BaoStockIndustryError(
            "BaoStock industry snapshot is missing: " + ", ".join(missing)
        )
    normalized = frame[list(required)].rename(
        columns={
            "updateDate": "industry_update_date",
            "code": "stock_id",
            "code_name": "security_name",
            "industryClassification": "industry_classification",
        }
    )
    normalized["industry_update_date"] = pd.to_datetime(
        normalized["industry_update_date"], errors="coerce"
    )
    normalized["snapshot_date"] = pd.Timestamp(snapshot_date)
    normalized["stock_id"] = normalized["stock_id"].astype(str).str.rsplit(".").str[-1]
    for column in ("security_name", "industry", "industry_classification"):
        normalized[column] = normalized[column].map(_repair_baostock_text)
    normalized = normalized.dropna(subset=["industry_update_date"])
    if normalized["industry_update_date"].gt(normalized["snapshot_date"]).any():
        raise BaoStockIndustryError("Industry update date is after snapshot date")
    if normalized["stock_id"].duplicated().any():
        raise BaoStockIndustryError("Industry snapshot contains duplicate stock codes")
    normalized = _add_industry_flags(normalized)
    return normalized.sort_values("stock_id").reset_index(drop=True)


def _write_manifest(
    path: Path,
    config: BaoStockIndustryConfig,
    records: list[dict[str, Any]],
    cache_hits: int,
) -> None:
    payload = {
        "provider": "BaoStock",
        "classification": "CSRC industry classification",
        "snapshot_frequency": "semiannual by default; point-in-time backward alignment",
        "requested_snapshots": len(config.snapshot_dates),
        "completed_snapshots": len(records),
        "rows": sum(int(record["rows"]) for record in records),
        "cache_hits": cache_hits,
        "dates": [record["snapshot_date"] for record in records],
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "status": (
            "complete" if len(records) == len(config.snapshot_dates) else "in_progress"
        ),
        "limitations": [
            "Semiannual snapshots may not capture intra-half-year industry changes immediately.",
            "Rows with blank BaoStock industry labels remain unclassified and are audited rather than guessed.",
        ],
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def build_baostock_industry_cache(
    config: BaoStockIndustryConfig,
) -> BaoStockIndustryResult:
    """Download resumable all-stock historical industry snapshots."""
    snapshot_directory = config.output_directory / "snapshots"
    snapshot_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = config.output_directory / "manifest.json"
    records: list[dict[str, Any]] = []
    pending: list[date] = []
    cache_hits = 0
    for snapshot_date in sorted(set(config.snapshot_dates)):
        path = industry_snapshot_path(snapshot_directory, snapshot_date)
        if path.exists() and not config.refresh:
            rows = len(pd.read_parquet(path, columns=["stock_id"]))
            records.append({"snapshot_date": snapshot_date.isoformat(), "rows": rows})
            cache_hits += 1
        else:
            pending.append(snapshot_date)
    _write_manifest(manifest_path, config, records, cache_hits)
    if pending:
        _login()
    try:
        for index, snapshot_date in enumerate(pending):
            last_error: Exception | None = None
            for attempt in range(1, 4):
                try:
                    result = bs.query_stock_industry(date=snapshot_date.isoformat())
                    frame = _normalize_industry_snapshot(
                        _paged_frame(result), snapshot_date
                    )
                    path = industry_snapshot_path(snapshot_directory, snapshot_date)
                    frame.to_parquet(path, index=False)
                    records.append(
                        {"snapshot_date": snapshot_date.isoformat(), "rows": len(frame)}
                    )
                    _write_manifest(manifest_path, config, records, cache_hits)
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < 3:
                        time.sleep(attempt)
            else:
                raise BaoStockIndustryError(
                    f"Failed to download industry snapshot for {snapshot_date}"
                ) from last_error
            if index + 1 < len(pending):
                time.sleep(config.pause_seconds)
    finally:
        if pending:
            try:
                bs.logout()
            except Exception:
                pass
    records.sort(key=lambda record: str(record["snapshot_date"]))
    _write_manifest(manifest_path, config, records, cache_hits)
    return BaoStockIndustryResult(
        snapshot_directory=snapshot_directory,
        manifest_path=manifest_path,
        requested_snapshots=len(config.snapshot_dates),
        completed_snapshots=len(records),
        rows=sum(int(record["rows"]) for record in records),
        cache_hits=cache_hits,
    )


def load_industry_snapshots(snapshot_directory: Path) -> pd.DataFrame:
    """Load and validate cached point-in-time industry snapshots."""
    paths = sorted(snapshot_directory.glob("industry_*.parquet"))
    if not paths:
        raise BaoStockIndustryError(
            f"No industry snapshots found in {snapshot_directory}"
        )
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    required = {"stock_id", "snapshot_date", "industry", "excluded_industry"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise BaoStockIndustryError("Industry cache is missing: " + ", ".join(missing))
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(6)
    for column in ("security_name", "industry", "industry_classification"):
        if column in frame:
            frame[column] = frame[column].map(_repair_baostock_text)
    frame = _add_industry_flags(frame)
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"], errors="coerce")
    if frame["snapshot_date"].isna().any():
        raise BaoStockIndustryError("Industry cache contains invalid snapshot dates")
    if frame.duplicated(["stock_id", "snapshot_date"]).any():
        raise BaoStockIndustryError("Industry cache contains duplicate stock-date rows")
    return frame.sort_values(["snapshot_date", "stock_id"]).reset_index(drop=True)


def align_industry_to_panel(
    panel: pd.DataFrame, industry_snapshots: pd.DataFrame
) -> pd.DataFrame:
    """Backward-align point-in-time industries to stock-month observations."""
    left = panel.copy()
    left["date"] = pd.to_datetime(left["date"], errors="coerce").astype(
        "datetime64[ns]"
    )
    if left["date"].isna().any():
        raise BaoStockIndustryError("Panel contains invalid dates")
    left["stock_id"] = left["stock_id"].astype(str).str.zfill(6)
    right = industry_snapshots.copy()
    right["stock_id"] = right["stock_id"].astype(str).str.zfill(6)
    right["snapshot_date"] = pd.to_datetime(
        right["snapshot_date"], errors="coerce"
    ).astype("datetime64[ns]")
    aligned = pd.merge_asof(
        left.sort_values(["date", "stock_id"]),
        right.sort_values(["snapshot_date", "stock_id"]),
        by="stock_id",
        left_on="date",
        right_on="snapshot_date",
        direction="backward",
    )
    return aligned.sort_values(["date", "stock_id"]).reset_index(drop=True)
