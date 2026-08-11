"""Auditable feature engineering for the thesis-style IVOL specification."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class ThesisIVOLDataError(ValueError):
    """Raised when a panel cannot support the declared thesis specification."""


@dataclass(frozen=True)
class ThesisIVOLConfig:
    lower_quantile: float = 0.01
    upper_quantile: float = 0.99
    microcap_fraction: float = 0.30

    def __post_init__(self) -> None:
        if not 0 <= self.lower_quantile < self.upper_quantile <= 1:
            raise ValueError(
                "Winsorization quantiles must satisfy 0 <= lower < upper <= 1"
            )
        if not 0 < self.microcap_fraction < 1:
            raise ValueError("microcap_fraction must be between 0 and 1")


def prepare_thesis_ivol_features(
    panel: pd.DataFrame,
    config: ThesisIVOLConfig | None = None,
    *,
    date_column: str = "date",
) -> pd.DataFrame:
    """Add turnover interaction, rank robustness, and microcap features.

    This transforms a research-ready monthly panel; it does not claim that a
    single-index BaoStock IVOL measure reproduces a CSMAR five-factor IVOL.
    """
    config = config or ThesisIVOLConfig()
    required = {date_column, "future_return", "IVOL", "turnover", "size", "bm"}
    missing = sorted(required - set(panel.columns))
    if missing:
        raise ThesisIVOLDataError(
            "Thesis IVOL features require columns: " + ", ".join(missing)
        )

    frame = panel.copy()
    frame[date_column] = pd.to_datetime(
        frame[date_column], errors="coerce", format="mixed"
    )
    if frame[date_column].isna().any():
        raise ThesisIVOLDataError("Thesis panel contains invalid observation dates")

    frame["future_return"] = pd.to_numeric(frame["future_return"], errors="coerce")
    frame["future_return_raw"] = frame["future_return"]
    continuous_features = ["IVOL", "turnover", "size", "bm"]
    for column in continuous_features:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame[f"{column}_raw"] = frame[column]
        lower = frame[column].quantile(config.lower_quantile)
        upper = frame[column].quantile(config.upper_quantile)
        frame[column] = frame[column].clip(lower=lower, upper=upper)

    grouped = frame.groupby(date_column, group_keys=False)
    frame["IVOL_c"] = frame["IVOL"] - grouped["IVOL"].transform("mean")
    frame["turnover_c"] = frame["turnover"] - grouped["turnover"].transform("mean")
    frame["ivol_turnover"] = frame["IVOL"] * frame["turnover"]
    frame["ivol_turnover_c"] = frame["IVOL_c"] * frame["turnover_c"]

    frame["IVOL_rank"] = grouped["IVOL"].rank(method="average", pct=True)
    frame["turnover_rank"] = grouped["turnover"].rank(method="average", pct=True)
    frame["IVOL_rank_c"] = frame["IVOL_rank"] - grouped["IVOL_rank"].transform("mean")
    frame["turnover_rank_c"] = frame["turnover_rank"] - grouped[
        "turnover_rank"
    ].transform("mean")
    frame["interaction_rank_c"] = frame["IVOL_rank_c"] * frame["turnover_rank_c"]

    size_cutoff = grouped["size"].transform(
        lambda values: values.quantile(config.microcap_fraction)
    )
    frame["microcap"] = frame["size"] <= size_cutoff
    return frame
