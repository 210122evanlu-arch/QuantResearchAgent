"""Strict local ingestion and monthly IVOL construction for five-factor data."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from tools.financial_data import compute_dataset_fingerprint, load_financial_data

FF5_COLUMNS = ("MKT", "SMB", "HML", "RMW", "CMA")


class FactorDataError(ValueError):
    """Raised when factor data cannot support a five-factor IVOL estimate."""


@dataclass(frozen=True)
class FactorDataConfig:
    path: Path
    date_column: str = "date"
    risk_free_column: str = "RF"
    values_in_percent: bool = False


@dataclass(frozen=True)
class CsmarFactorDataConfig:
    """Select one auditable specification from CSMAR's multi-panel export."""

    path: Path
    market_type: str = "P9709"
    portfolios: int = 1
    weighting: Literal["float_market_cap", "total_market_cap"] = "float_market_cap"
    risk_free_path: Path | None = None
    risk_free_date_column: str = "date"
    risk_free_rate_column: str = "RF"
    risk_free_values_in_percent: bool = False
    reproduce_original_workflow: bool = False


@dataclass(frozen=True)
class FactorDataSet:
    frame: pd.DataFrame
    fingerprint: str
    source_path: Path
    metadata: dict[str, str | int | bool] = field(default_factory=dict)


def _configured_fingerprint(path: Path, configuration: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(compute_dataset_fingerprint(path).encode())
    digest.update(
        json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()
    )
    return f"sha256:{digest.hexdigest()}"


def load_five_factor_data(config: FactorDataConfig) -> FactorDataSet:
    """Load validated daily factors without guessing units."""
    frame = load_financial_data(config.path).copy()
    required = {config.date_column, config.risk_free_column, *FF5_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise FactorDataError("Five-factor data is missing: " + ", ".join(missing))
    frame["date"] = pd.to_datetime(
        frame[config.date_column], errors="coerce", format="mixed"
    )
    if frame["date"].isna().any():
        raise FactorDataError("Five-factor data contains invalid dates")
    if frame["date"].duplicated().any():
        raise FactorDataError("Five-factor data contains duplicate dates")
    numeric_columns = [*FF5_COLUMNS, config.risk_free_column]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[numeric_columns].isna().any().any():
        raise FactorDataError("Five-factor data contains missing or nonnumeric values")
    if config.values_in_percent:
        frame[numeric_columns] = frame[numeric_columns] / 100.0
    frame = frame.rename(columns={config.risk_free_column: "RF"})
    return FactorDataSet(
        frame=frame[["date", *FF5_COLUMNS, "RF"]].sort_values("date"),
        fingerprint=compute_dataset_fingerprint(config.path),
        source_path=config.path.resolve(),
        metadata={
            "provider": "generic",
            "return_basis": "excess_return",
            "residual_ddof": 1,
        },
    )


def load_csmar_five_factor_data(config: CsmarFactorDataConfig) -> FactorDataSet:
    """Load one CSMAR daily FF5 series with an explicit risk-free convention."""
    frame = load_financial_data(config.path).copy()
    suffix = "1" if config.weighting == "float_market_cap" else "2"
    source_columns = {
        "RiskPremium" + suffix: "MKT",
        "SMB" + suffix: "SMB",
        "HML" + suffix: "HML",
        "RMW" + suffix: "RMW",
        "CMA" + suffix: "CMA",
    }
    required = {"MarkettypeID", "TradingDate", "Portfolios", *source_columns}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise FactorDataError(
            "CSMAR five-factor data is missing: " + ", ".join(missing)
        )

    selected = frame.loc[
        (frame["MarkettypeID"].astype(str) == config.market_type)
        & (pd.to_numeric(frame["Portfolios"], errors="coerce") == config.portfolios)
    ].copy()
    if selected.empty:
        raise FactorDataError(
            "No CSMAR rows match market_type="
            f"{config.market_type!r}, portfolios={config.portfolios}"
        )
    selected["date"] = pd.to_datetime(
        selected["TradingDate"], errors="coerce", format="mixed"
    )
    if selected["date"].isna().any():
        raise FactorDataError("CSMAR five-factor data contains invalid dates")
    if selected["date"].duplicated().any():
        raise FactorDataError("Selected CSMAR five-factor series has duplicate dates")
    selected = selected.rename(columns=source_columns)
    for column in FF5_COLUMNS:
        selected[column] = pd.to_numeric(selected[column], errors="coerce")
    if selected[list(FF5_COLUMNS)].isna().any().any():
        raise FactorDataError(
            "Selected CSMAR five-factor series contains missing values"
        )

    return_basis = "excess_return"
    risk_free_fingerprint = ""
    if config.risk_free_path is not None:
        risk_free = load_financial_data(config.risk_free_path).copy()
        risk_required = {
            config.risk_free_date_column,
            config.risk_free_rate_column,
        }
        risk_missing = sorted(risk_required - set(risk_free.columns))
        if risk_missing:
            raise FactorDataError(
                "Risk-free data is missing: " + ", ".join(risk_missing)
            )
        risk_free["date"] = pd.to_datetime(
            risk_free[config.risk_free_date_column], errors="coerce", format="mixed"
        )
        risk_free["RF"] = pd.to_numeric(
            risk_free[config.risk_free_rate_column], errors="coerce"
        )
        if risk_free[["date", "RF"]].isna().any().any():
            raise FactorDataError("Risk-free data contains invalid dates or values")
        if risk_free["date"].duplicated().any():
            raise FactorDataError("Risk-free data contains duplicate dates")
        if config.risk_free_values_in_percent:
            risk_free["RF"] = risk_free["RF"] / 100.0
        selected = selected.merge(
            risk_free[["date", "RF"]], on="date", how="left", validate="one_to_one"
        )
        if selected["RF"].isna().any():
            raise FactorDataError(
                "Risk-free data does not cover the CSMAR factor series"
            )
        risk_free_fingerprint = compute_dataset_fingerprint(config.risk_free_path)
    elif config.reproduce_original_workflow:
        selected["RF"] = 0.0
        return_basis = "raw_return_original_replication"
    else:
        raise FactorDataError(
            "CSMAR export has no RF column; provide risk_free_path or explicitly set "
            "reproduce_original_workflow=True"
        )

    fingerprint_configuration = {
        "market_type": config.market_type,
        "portfolios": config.portfolios,
        "weighting": config.weighting,
        "return_basis": return_basis,
        "risk_free_fingerprint": risk_free_fingerprint,
    }
    return FactorDataSet(
        frame=selected[["date", *FF5_COLUMNS, "RF"]].sort_values("date"),
        fingerprint=_configured_fingerprint(config.path, fingerprint_configuration),
        source_path=config.path.resolve(),
        metadata={
            "provider": "CSMAR",
            "market_type": config.market_type,
            "portfolios": config.portfolios,
            "weighting": config.weighting,
            "return_basis": return_basis,
            "residual_ddof": 0 if config.reproduce_original_workflow else 1,
        },
    )


def prepare_five_factor_ivol_panel(
    stock_daily: pd.DataFrame,
    factors: FactorDataSet,
    *,
    minimum_daily_observations: int = 15,
) -> pd.DataFrame:
    """Estimate monthly FF5 residual volatility and next-month excess returns."""
    if minimum_daily_observations < 8:
        raise ValueError("minimum_daily_observations must be at least 8")
    required = {"stock_id", "date", "return", "turnover", "size", "bm"}
    missing = sorted(required - set(stock_daily.columns))
    if missing:
        raise FactorDataError("Daily stock data is missing: " + ", ".join(missing))

    daily = stock_daily.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce", format="mixed")
    if daily["date"].isna().any():
        raise FactorDataError("Daily stock data contains invalid dates")
    numeric = ["return", "turnover", "size", "bm"]
    for column in numeric:
        daily[column] = pd.to_numeric(daily[column], errors="coerce")
    merged = daily.merge(factors.frame, on="date", how="left", validate="many_to_one")
    factor_columns = [*FF5_COLUMNS, "RF"]
    if merged[factor_columns].isna().any().any():
        missing_dates = merged.loc[
            merged[factor_columns].isna().any(axis=1), "date"
        ].drop_duplicates()
        preview = ", ".join(date.strftime("%Y-%m-%d") for date in missing_dates[:5])
        raise FactorDataError(
            "Five-factor data does not cover all stock dates; missing: " + preview
        )
    merged["excess_return"] = merged["return"] - merged["RF"]
    merged["month"] = merged["date"].dt.to_period("M")
    merged = merged.sort_values(["stock_id", "date"])

    rows: list[dict[str, Any]] = []
    for (stock_id, _month), group in merged.groupby(["stock_id", "month"]):
        regression = group[["excess_return", *FF5_COLUMNS]].dropna()
        if len(regression) < minimum_daily_observations:
            continue
        design = np.column_stack(
            [np.ones(len(regression)), regression[list(FF5_COLUMNS)].to_numpy(float)]
        )
        if np.linalg.matrix_rank(design) < design.shape[1]:
            continue
        excess = regression["excess_return"].to_numpy(float)
        coefficients = np.linalg.lstsq(design, excess, rcond=None)[0]
        residuals = excess - design @ coefficients
        residual_ddof = int(factors.metadata.get("residual_ddof", 1))
        latest = group.iloc[-1]
        valid_returns = group["return"].dropna().to_numpy(float)
        risk_free = group.loc[group["return"].notna(), "RF"].to_numpy(float)
        rows.append(
            {
                "stock_id": str(stock_id),
                "date": group["date"].max(),
                "monthly_return": float(np.prod(1.0 + valid_returns) - 1.0),
                "monthly_rf": float(np.prod(1.0 + risk_free) - 1.0),
                "IVOL": float(np.std(residuals, ddof=residual_ddof)),
                "turnover": float(group["turnover"].sum(min_count=1)),
                "size": float(latest["size"]),
                "bm": float(latest["bm"]),
                "daily_observations": len(regression),
                "ivol_model": "fama_french_five_factor",
                "factor_fingerprint": factors.fingerprint,
                "factor_provider": str(factors.metadata.get("provider", "unknown")),
                "return_basis": str(
                    factors.metadata.get("return_basis", "excess_return")
                ),
                "residual_ddof": residual_ddof,
            }
        )
    panel = pd.DataFrame(rows)
    if panel.empty:
        raise FactorDataError("No stock-month supports five-factor IVOL estimation")
    panel = panel.sort_values(["stock_id", "date"]).reset_index(drop=True)
    grouped = panel.groupby("stock_id", group_keys=False)
    panel["target_date"] = grouped["date"].shift(-1)
    panel["future_return"] = grouped["monthly_return"].shift(-1) - grouped[
        "monthly_rf"
    ].shift(-1)
    return panel.dropna(subset=["target_date", "future_return"]).reset_index(drop=True)
