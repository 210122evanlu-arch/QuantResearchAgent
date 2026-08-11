"""Build an auditable monthly panel for the corrected IVOL thesis replication.

The legacy notebook accidentally defined stock return as the percentage change
in market capitalisation.  This module deliberately keeps returns, market
capitalisation, book-to-market, and turnover as separate source pipelines.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from data_sources.baostock_industry import (
    align_industry_to_panel,
    load_industry_snapshots,
)
from data_sources.baostock_returns import (
    align_baostock_future_returns,
    load_baostock_monthly_returns,
)
from data_sources.fama_french import FF5_COLUMNS
from data_sources.risk_free import align_risk_free_to_dates, load_risk_free_proxy
from tools.financial_data import compute_dataset_fingerprint

LOGGER = logging.getLogger(__name__)


class ThesisV2DataError(ValueError):
    """Raised when a source cannot satisfy the corrected panel contract."""


@dataclass(frozen=True)
class ThesisV2Config:
    daily_directory: Path
    factor_path: Path
    market_cap_paths: tuple[Path, ...]
    pb_paths: tuple[Path, ...]
    turnover_path: Path
    universe_path: Path | None = None
    cache_directory: Path | None = None
    baostock_monthly_return_directory: Path | None = None
    risk_free_path: Path | None = None
    risk_free_max_staleness_days: int = 7
    industry_snapshot_directory: Path | None = None
    start_date: str = "2010-01-01"
    end_date: str = "2025-12-31"
    minimum_daily_observations: int = 15
    residual_ddof: int = 1
    exclude_st: bool = True
    require_month_end_trading: bool = True
    exclude_recent_listings_days: int = 365
    main_board_daily_return_limit: float = 0.115
    growth_board_daily_return_limit: float = 0.215

    def __post_init__(self) -> None:
        if self.minimum_daily_observations < 8:
            raise ValueError("minimum_daily_observations must be at least 8")
        if self.residual_ddof not in (0, 1):
            raise ValueError("residual_ddof must be 0 or 1")
        if self.exclude_recent_listings_days < 0:
            raise ValueError("exclude_recent_listings_days must be nonnegative")
        if self.risk_free_max_staleness_days < 0:
            raise ValueError("risk_free_max_staleness_days must be nonnegative")
        if not 0 < self.main_board_daily_return_limit < 1:
            raise ValueError("main_board_daily_return_limit must be between 0 and 1")
        if not 0 < self.growth_board_daily_return_limit < 1:
            raise ValueError("growth_board_daily_return_limit must be between 0 and 1")


def normalize_stock_code(value: object) -> str:
    """Normalize CSMAR, BaoStock, and filename identifiers to six digits."""
    text = str(value).strip().lower()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(character for character in text if character.isdigit())
    return digits[-6:].zfill(6)


def is_p9709_stock(code: str) -> bool:
    """Return whether a code matches CSMAR P9709's SH/SZ A-share scope.

    P9709 covers Shanghai and Shenzhen A shares including ChiNext, but excludes
    STAR Market and Beijing Stock Exchange securities.
    """
    normalized = normalize_stock_code(code)
    return normalized.startswith(
        ("000", "001", "002", "003", "300", "301", "600", "601", "603", "605")
    )


def _month_number(periods: pd.Series) -> pd.Series:
    return periods.dt.year * 12 + periods.dt.month


def _compound_returns(values: pd.Series) -> float:
    numeric = values.to_numpy(dtype=float)
    return float(np.prod(1.0 + numeric) - 1.0)


def _estimate_stock_months(
    path: Path,
    factors: pd.DataFrame,
    config: ThesisV2Config,
) -> list[dict[str, Any]]:
    factors = factors.copy()
    if "RF" not in factors:
        factors["RF"] = 0.0
    stock_code = normalize_stock_code(path.stem)
    if not is_p9709_stock(stock_code):
        return []

    raw = pd.read_csv(path, usecols=[0, 3])
    if raw.shape[1] != 2:
        raise ThesisV2DataError(f"Unexpected AKShare columns in {path}")
    raw.columns = ["date", "close"]
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw["close"] = pd.to_numeric(raw["close"], errors="coerce")
    raw = raw.dropna().sort_values("date").drop_duplicates("date", keep="last")
    raw = raw.loc[
        raw["date"].between(
            pd.Timestamp(config.start_date), pd.Timestamp(config.end_date)
        )
    ].copy()
    if raw.empty:
        return []

    first_observed_date = raw["date"].min()
    positive_close = raw["close"].where(raw["close"].gt(0))
    raw["raw_return"] = positive_close.pct_change(fill_method=None)
    growth_board = stock_code.startswith(("300", "301")) & raw["date"].ge(
        pd.Timestamp("2020-08-24")
    )
    return_limit = pd.Series(
        np.where(
            growth_board,
            config.growth_board_daily_return_limit,
            config.main_board_daily_return_limit,
        ),
        index=raw.index,
    )
    missing_price_link = raw["raw_return"].isna() & raw["date"].ne(first_observed_date)
    raw["invalid_daily_return"] = (
        raw["close"].le(0)
        | missing_price_link
        | raw["raw_return"].abs().gt(return_limit)
    )
    raw["return"] = raw["raw_return"].mask(raw["invalid_daily_return"])
    merged = raw.merge(factors, on="date", how="left", validate="one_to_one")
    merged["month"] = merged["date"].dt.to_period("M")

    regression = merged[["month", "return", "RF", *FF5_COLUMNS]].dropna()
    if regression.empty:
        return []
    month_codes, months = pd.factorize(regression["month"], sort=True)
    design = np.column_stack(
        [np.ones(len(regression)), regression[list(FF5_COLUMNS)].to_numpy(float)]
    )
    returns = (regression["return"] - regression["RF"]).to_numpy(float)
    group_count = len(months)
    cross_products = np.zeros((group_count, design.shape[1], design.shape[1]))
    cross_returns = np.zeros((group_count, design.shape[1]))
    squared_returns = np.zeros(group_count)
    np.add.at(cross_products, month_codes, design[:, :, None] * design[:, None, :])
    np.add.at(cross_returns, month_codes, design * returns[:, None])
    np.add.at(squared_returns, month_codes, returns**2)
    observations = np.bincount(month_codes, minlength=group_count)
    eligible = observations >= config.minimum_daily_observations

    coefficients = np.full((group_count, design.shape[1]), np.nan)
    eligible_positions = np.flatnonzero(eligible)
    if len(eligible_positions):
        try:
            coefficients[eligible_positions] = np.linalg.solve(
                cross_products[eligible_positions],
                cross_returns[eligible_positions, :, None],
            )[..., 0]
        except np.linalg.LinAlgError:
            for position in eligible_positions:
                try:
                    coefficients[position] = np.linalg.solve(
                        cross_products[position], cross_returns[position]
                    )
                except np.linalg.LinAlgError:
                    eligible[position] = False

    residual_sum_squares = squared_returns - np.einsum(
        "ij,ij->i", coefficients, cross_returns
    )
    denominators = observations - config.residual_ddof
    ivol = np.sqrt(np.maximum(residual_sum_squares, 0.0) / denominators)
    ivol[~eligible] = np.nan

    regression_summary = pd.DataFrame(
        {
            "month": pd.PeriodIndex(months, freq="M"),
            "IVOL": ivol,
            "daily_observations": observations,
        }
    ).dropna(subset=["IVOL"])
    monthly = (
        merged.groupby("month", sort=True)
        .agg(
            date=("date", "max"),
            monthly_return=(
                "return",
                lambda values: (1.0 + values.dropna()).prod() - 1.0,
            ),
            invalid_daily_returns=("invalid_daily_return", "sum"),
        )
        .reset_index()
    )
    monthly = monthly.merge(regression_summary, on="month", validate="one_to_one")
    monthly.loc[monthly["invalid_daily_returns"].gt(0), "IVOL"] = np.nan
    monthly["stock_id"] = stock_code
    monthly["first_observed_date"] = first_observed_date
    if first_observed_date <= pd.Timestamp(config.start_date) + pd.Timedelta(days=31):
        monthly["listing_age_days"] = np.nan
    else:
        monthly["listing_age_days"] = (monthly["date"] - first_observed_date).dt.days
    return cast(
        list[dict[str, Any]],
        monthly[
            [
                "stock_id",
                "month",
                "date",
                "monthly_return",
                "IVOL",
                "daily_observations",
                "invalid_daily_returns",
                "first_observed_date",
                "listing_age_days",
            ]
        ].to_dict("records"),
    )


def build_return_ivol_panel(config: ThesisV2Config) -> pd.DataFrame:
    """Build true monthly returns and FF5 IVOL from AKShare daily close files."""
    cache_name = "return_ivol_v2_exchange_limits.parquet"
    if config.risk_free_path is not None:
        fingerprint = compute_dataset_fingerprint(config.risk_free_path)
        cache_name = f"return_ivol_v4_rf_{fingerprint[-12:]}.parquet"
    cache_path = (
        config.cache_directory / cache_name
        if config.cache_directory is not None
        else None
    )
    if cache_path is not None and cache_path.exists():
        LOGGER.info("Loading cached return/IVOL panel from %s", cache_path)
        cached = pd.read_parquet(cache_path)
        cached["month"] = pd.PeriodIndex(cached["month"], freq="M")
        cached["target_month"] = pd.PeriodIndex(cached["target_month"], freq="M")
        if "monthly_rf" not in cached:
            cached["monthly_rf"] = 0.0
            cached["future_rf"] = 0.0
        return cached
    factors = pd.read_parquet(config.factor_path).copy()
    required = {"date", *FF5_COLUMNS}
    missing = sorted(required - set(factors.columns))
    if missing:
        raise ThesisV2DataError("Factor data is missing: " + ", ".join(missing))
    factors["date"] = pd.to_datetime(factors["date"], errors="coerce")
    factors = factors[["date", *FF5_COLUMNS]].dropna().drop_duplicates("date")
    if config.risk_free_path is not None:
        risk_free = load_risk_free_proxy(config.risk_free_path)
        aligned_rf = align_risk_free_to_dates(
            factors["date"],
            risk_free,
            max_staleness_days=config.risk_free_max_staleness_days,
        )
        factors = factors.merge(
            aligned_rf[["date", "RF"]], on="date", how="left", validate="one_to_one"
        )
    else:
        factors["RF"] = 0.0

    paths = sorted(config.daily_directory.glob("*.csv"))
    if not paths:
        raise ThesisV2DataError(f"No daily CSV files found in {config.daily_directory}")
    rows: list[dict[str, Any]] = []
    processed = 0
    for path in paths:
        if not is_p9709_stock(path.stem):
            continue
        rows.extend(_estimate_stock_months(path, factors, config))
        processed += 1
        if processed % 500 == 0:
            LOGGER.info("Processed %s P9709 daily stock files", processed)
    panel = pd.DataFrame(rows)
    if panel.empty:
        raise ThesisV2DataError("No stock-month supports the IVOL specification")
    invalid_daily_total = int(panel["invalid_daily_returns"].sum())
    invalid_month_total = int(panel["IVOL"].isna().sum())
    panel = panel.loc[panel["IVOL"].notna()].copy()
    monthly_rf = (
        factors.assign(month=factors["date"].dt.to_period("M"))
        .groupby("month", as_index=False)
        .agg(monthly_rf=("RF", _compound_returns))
    )
    panel = panel.merge(monthly_rf, on="month", how="left", validate="many_to_one")
    if panel["monthly_rf"].isna().any():
        raise ThesisV2DataError("Risk-free proxy does not cover every IVOL month")
    panel["source_invalid_daily_observations_total"] = invalid_daily_total
    panel["source_invalid_stock_months_total"] = invalid_month_total
    panel = panel.sort_values(["stock_id", "month"]).reset_index(drop=True)

    grouped = panel.groupby("stock_id", sort=False)
    panel["target_date"] = grouped["date"].shift(-1)
    panel["target_month"] = grouped["month"].shift(-1)
    panel["future_return"] = grouped["monthly_return"].shift(-1)
    monthly_rf_lookup = monthly_rf.set_index("month")["monthly_rf"]
    panel["future_rf"] = (panel["month"] + 1).map(monthly_rf_lookup)
    current_number = panel["month"].dt.year * 12 + panel["month"].dt.month
    target_number = panel["target_month"].dt.year * 12 + panel["target_month"].dt.month
    panel["target_is_next_calendar_month"] = target_number.eq(current_number + 1)
    panel.loc[~panel["target_is_next_calendar_month"], "future_return"] = np.nan
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        serializable = panel.copy()
        serializable["month"] = serializable["month"].astype(str)
        serializable["target_month"] = serializable["target_month"].astype(str)
        serializable.to_parquet(cache_path, index=False)
        LOGGER.info("Saved return/IVOL cache to %s", cache_path)
    return panel


def _load_month_end_values(
    paths: Iterable[Path],
    *,
    code_column: str,
    date_column: str,
    value_column: str,
    output_column: str,
) -> pd.DataFrame:
    candidates: list[pd.DataFrame] = []
    for path in paths:
        chunk = pd.read_csv(
            path,
            usecols=[code_column, date_column, value_column],
            dtype={code_column: str},
        )
        chunk = chunk.rename(
            columns={
                code_column: "stock_id",
                date_column: "date",
                value_column: output_column,
            }
        )
        chunk["stock_id"] = chunk["stock_id"].map(normalize_stock_code)
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce")
        chunk[output_column] = pd.to_numeric(chunk[output_column], errors="coerce")
        chunk = chunk.dropna(subset=["date", output_column])
        chunk["month"] = chunk["date"].dt.to_period("M")
        last = (
            chunk.sort_values("date")
            .groupby(["stock_id", "month"], as_index=False, sort=False)
            .tail(1)
        )
        candidates.append(last[["stock_id", "month", "date", output_column]])
    if not candidates:
        raise ThesisV2DataError(f"No source files supplied for {output_column}")
    combined = pd.concat(candidates, ignore_index=True)
    combined = (
        combined.sort_values("date")
        .groupby(["stock_id", "month"], as_index=False, sort=False)
        .tail(1)
    )
    return combined[["stock_id", "month", output_column]].reset_index(drop=True)


def load_monthly_market_cap(paths: Iterable[Path]) -> pd.DataFrame:
    """Load CSMAR month-end total market value (Dsmvtll)."""
    frame = _load_month_end_values(
        paths,
        code_column="Stkcd",
        date_column="Trddt",
        value_column="Dsmvtll",
        output_column="market_cap",
    )
    frame = frame.loc[frame["market_cap"].gt(0)].copy()
    frame["size"] = np.log(frame["market_cap"])
    return frame


def load_monthly_book_to_market(paths: Iterable[Path]) -> pd.DataFrame:
    """Load CSMAR month-end PB and derive BM only for positive book equity."""
    frame = _load_month_end_values(
        paths,
        code_column="Symbol",
        date_column="TradingDate",
        value_column="PB",
        output_column="pb",
    )
    frame = frame.loc[frame["pb"].gt(0)].copy()
    frame["bm"] = 1.0 / frame["pb"]
    return frame


def load_monthly_turnover(path: Path) -> pd.DataFrame:
    """Load CSMAR monthly float-share turnover despite its broken XLSX dimension."""
    frame = pd.read_excel(
        path,
        usecols=["Stkcd", "Trdmnt", "ToverOsM", "ToverTlM"],
        skiprows=[1, 2],
        dtype={"Stkcd": str, "Trdmnt": str},
        engine="openpyxl",
    )
    frame = frame.rename(columns={"Stkcd": "stock_id", "ToverOsM": "turnover"})
    frame["stock_id"] = frame["stock_id"].map(normalize_stock_code)
    frame["month"] = pd.to_datetime(frame["Trdmnt"], errors="coerce").dt.to_period("M")
    frame["turnover"] = pd.to_numeric(frame["turnover"], errors="coerce")
    frame["turnover_total_shares"] = pd.to_numeric(frame["ToverTlM"], errors="coerce")
    frame = frame.dropna(subset=["month", "turnover"])
    if frame.duplicated(["stock_id", "month"]).any():
        raise ThesisV2DataError("CSMAR turnover contains duplicate stock-month rows")
    return frame[["stock_id", "month", "turnover", "turnover_total_shares"]]


def load_monthly_universe(path: Path) -> pd.DataFrame:
    """Normalize monthly BaoStock names, trading state, and ST indicators."""
    frame = pd.read_parquet(path).copy()
    required = {
        "date",
        "stock_id",
        "security_name",
        "trade_status",
        "special_treatment",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ThesisV2DataError("Universe data is missing: " + ", ".join(missing))
    frame["stock_id"] = frame["stock_id"].map(normalize_stock_code)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["month"] = frame["date"].dt.to_period("M")
    frame = (
        frame.sort_values("date")
        .groupby(["stock_id", "month"], as_index=False, sort=False)
        .tail(1)
    )
    return frame[
        ["stock_id", "month", "security_name", "trade_status", "special_treatment"]
    ]


def assemble_thesis_v2_panel(
    return_ivol: pd.DataFrame,
    market_cap: pd.DataFrame,
    book_to_market: pd.DataFrame,
    turnover: pd.DataFrame,
    config: ThesisV2Config,
    universe: pd.DataFrame | None = None,
    industry_snapshots: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Merge sources, apply point-in-time filters, and return an audit trail."""
    audit: dict[str, Any] = {
        "return_ivol_rows": len(return_ivol),
        "invalid_daily_observations_detected": int(
            return_ivol.get(
                "source_invalid_daily_observations_total", pd.Series([0])
            ).max()
        ),
        "invalid_stock_months_excluded": int(
            return_ivol.get("source_invalid_stock_months_total", pd.Series([0])).max()
        ),
    }
    panel = return_ivol.copy()
    panel = panel.loc[panel["future_return"].notna()].copy()
    audit["rows_with_consecutive_future_return"] = len(panel)

    panel = panel.merge(
        market_cap[["stock_id", "month", "market_cap", "size"]],
        on=["stock_id", "month"],
        how="inner",
        validate="one_to_one",
    )
    audit["rows_after_market_cap"] = len(panel)
    panel = panel.merge(
        book_to_market[["stock_id", "month", "pb", "bm"]],
        on=["stock_id", "month"],
        how="inner",
        validate="one_to_one",
    )
    audit["rows_after_book_to_market"] = len(panel)
    panel = panel.merge(
        turnover,
        on=["stock_id", "month"],
        how="inner",
        validate="one_to_one",
    )
    audit["rows_after_turnover"] = len(panel)

    if universe is not None:
        panel = panel.merge(
            universe,
            on=["stock_id", "month"],
            how="inner",
            validate="one_to_one",
        )
        audit["rows_after_historical_universe_match"] = len(panel)
        if config.require_month_end_trading:
            before = len(panel)
            panel = panel.loc[panel["trade_status"].astype(str).eq("1")].copy()
            audit["excluded_month_end_not_trading"] = int(before - len(panel))
        if config.exclude_st:
            before = len(panel)
            panel = panel.loc[~panel["special_treatment"].astype(bool)].copy()
            audit["excluded_st_months"] = int(before - len(panel))

    if config.exclude_recent_listings_days:
        before = len(panel)
        recent = panel["listing_age_days"].notna() & panel["listing_age_days"].lt(
            config.exclude_recent_listings_days
        )
        panel = panel.loc[~recent].copy()
        audit["excluded_recent_listing_proxy"] = int(before - len(panel))

    if industry_snapshots is not None:
        panel = align_industry_to_panel(panel, industry_snapshots)
        known_industry = panel["industry"].fillna("").astype(str).str.strip().ne("")
        audit["rows_with_known_historical_industry"] = int(known_industry.sum())
        audit["rows_without_known_historical_industry"] = int((~known_industry).sum())
        financial = panel["financial_industry"].fillna(False).astype(bool)
        real_estate = panel["real_estate_industry"].fillna(False).astype(bool)
        audit["excluded_financial_industry"] = int(financial.sum())
        audit["excluded_real_estate_industry"] = int(real_estate.sum())
        before = len(panel)
        panel = panel.loc[~(financial | real_estate)].copy()
        audit["excluded_financial_and_real_estate"] = int(before - len(panel))

    required_numeric = ["future_return", "IVOL", "turnover", "size", "bm"]
    panel = panel.replace([np.inf, -np.inf], np.nan).dropna(subset=required_numeric)
    panel["date"] = panel["month"].dt.to_timestamp("M")
    panel["year_month"] = panel["month"].astype(str)
    panel["stkcd"] = panel["stock_id"]
    panel["ivol"] = panel["IVOL"]
    panel["ln_size"] = panel["size"]
    panel["next_ret"] = panel["future_return"]
    panel = panel.sort_values(["date", "stock_id"]).reset_index(drop=True)

    audit.update(
        {
            "final_rows": len(panel),
            "unique_stocks": int(panel["stock_id"].nunique()),
            "start_month": str(panel["month"].min()),
            "end_month": str(panel["month"].max()),
            "duplicate_stock_months": int(
                panel.duplicated(["stock_id", "month"]).sum()
            ),
            "missing_required_values": int(panel[required_numeric].isna().sum().sum()),
            "look_ahead_violations": int((panel["target_date"] <= panel["date"]).sum()),
            "return_source": "AKShare qfq close, compounded from validated daily pct_change",
            "factor_scope": "CSMAR P9709, 2x3, float-market-cap weighted",
            "risk_free_treatment": (
                "ChinaBond three-month government-yield proxy; daily stock excess return used for IVOL and next-month RF deducted from the target"
                if config.risk_free_path is not None
                else "RF unavailable in supplied factor export; raw stock return used with regression intercept"
            ),
            "risk_free_source": (
                str(config.risk_free_path)
                if config.risk_free_path is not None
                else None
            ),
            "risk_free_fingerprint": (
                compute_dataset_fingerprint(config.risk_free_path)
                if config.risk_free_path is not None
                else None
            ),
            "residual_ddof": config.residual_ddof,
            "main_board_daily_return_limit": config.main_board_daily_return_limit,
            "growth_board_daily_return_limit": config.growth_board_daily_return_limit,
            "daily_return_filter_reason": "Supplied qfq histories contain negative/near-zero adjusted prices and mechanical returns beyond exchange limits; any affected stock-month is excluded rather than winsorized",
            "turnover_definition": "CSMAR ToverOsM: sum of daily float-share turnover within month, percent",
            "size_definition": "natural log of CSMAR month-end Dsmvtll",
            "bm_definition": "1 / positive CSMAR month-end PB",
            "known_survivorship_limitation": "AKShare daily directory was collected from a contemporary stock list; delisted firms absent from that list may be missing",
            "historical_industry_filter_applied": industry_snapshots is not None,
            "historical_industry_source": (
                str(config.industry_snapshot_directory)
                if config.industry_snapshot_directory is not None
                else None
            ),
        }
    )
    return panel, audit


def build_thesis_v2_dataset(
    config: ThesisV2Config,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Execute all corrected source pipelines and produce a research-ready panel."""
    return_ivol = build_return_ivol_panel(config)
    target_audit: dict[str, Any] = {}
    if config.baostock_monthly_return_directory is not None:
        monthly_returns = load_baostock_monthly_returns(
            config.baostock_monthly_return_directory
        )
        return_ivol, target_audit = align_baostock_future_returns(
            return_ivol, monthly_returns
        )
    if config.risk_free_path is not None:
        if "future_rf" not in return_ivol:
            raise ThesisV2DataError("Return/IVOL panel is missing future_rf")
        return_ivol["future_return_raw"] = return_ivol["future_return"]
        return_ivol["future_return"] = (
            return_ivol["future_return"] - return_ivol["future_rf"]
        )
    market_cap = load_monthly_market_cap(config.market_cap_paths)
    book_to_market = load_monthly_book_to_market(config.pb_paths)
    turnover = load_monthly_turnover(config.turnover_path)
    universe = (
        load_monthly_universe(config.universe_path) if config.universe_path else None
    )
    industry_snapshots = (
        load_industry_snapshots(config.industry_snapshot_directory)
        if config.industry_snapshot_directory is not None
        else None
    )
    panel, audit = assemble_thesis_v2_panel(
        return_ivol,
        market_cap,
        book_to_market,
        turnover,
        config,
        universe,
        industry_snapshots,
    )
    audit.update(target_audit)
    audit["target_return_provider"] = (
        "BaoStock pctChg, unadjusted monthly"
        if config.baostock_monthly_return_directory is not None
        else "AKShare qfq close, validated daily compounding"
    )
    audit["generated_at_utc"] = datetime.now(UTC).isoformat()
    audit["configuration"] = {
        key: (
            [str(item) for item in value]
            if isinstance(value, tuple)
            else str(value)
            if isinstance(value, Path)
            else value
        )
        for key, value in asdict(config).items()
    }
    return panel, audit


def save_thesis_v2_dataset(
    panel: pd.DataFrame,
    audit: dict[str, Any],
    output_directory: Path,
    *,
    stem: str = "molly_regression_final_v2",
) -> tuple[Path, Path]:
    """Persist the panel and its adjacent machine-readable audit manifest."""
    output_directory.mkdir(parents=True, exist_ok=True)
    panel_path = output_directory / f"{stem}.parquet"
    audit_path = output_directory / f"{stem}.audit.json"
    serializable = panel.copy()
    for column in ("month", "target_month"):
        if column in serializable:
            serializable[column] = serializable[column].astype(str)
    serializable.to_parquet(panel_path, index=False)
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return panel_path, audit_path
