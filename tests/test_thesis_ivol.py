import pandas as pd
import pytest

from tools.thesis_ivol import (
    ThesisIVOLConfig,
    ThesisIVOLDataError,
    prepare_thesis_ivol_features,
)


def _panel() -> pd.DataFrame:
    rows = []
    for month in ("2024-01-31", "2024-02-29"):
        for index in range(10):
            rows.append(
                {
                    "stock_id": f"S{index:02d}",
                    "date": month,
                    "future_return": index / 100,
                    "IVOL": 0.01 + index / 1000,
                    "turnover": 1.0 + index,
                    "size": 10.0 + index,
                    "bm": 0.2 + index / 100,
                }
            )
    return pd.DataFrame(rows)


def test_thesis_features_create_interactions_ranks_and_microcaps() -> None:
    result = prepare_thesis_ivol_features(_panel())

    assert {
        "IVOL_c",
        "turnover_c",
        "ivol_turnover_c",
        "interaction_rank_c",
        "microcap",
        "IVOL_raw",
    }.issubset(result.columns)
    assert result.groupby("date")["IVOL_c"].mean().abs().max() < 1e-12
    assert result.groupby("date")["turnover_c"].mean().abs().max() < 1e-12
    assert result.groupby("date")["microcap"].sum().eq(3).all()
    assert result["future_return"].equals(result["future_return_raw"])


def test_thesis_features_require_turnover() -> None:
    with pytest.raises(ThesisIVOLDataError, match="turnover"):
        prepare_thesis_ivol_features(_panel().drop(columns="turnover"))


def test_thesis_feature_config_rejects_invalid_ranges() -> None:
    with pytest.raises(ValueError, match="Winsorization"):
        ThesisIVOLConfig(lower_quantile=0.9, upper_quantile=0.1)
    with pytest.raises(ValueError, match="microcap_fraction"):
        ThesisIVOLConfig(microcap_fraction=1.0)


def test_thesis_features_reject_invalid_dates() -> None:
    panel = _panel()
    panel.loc[0, "date"] = "not-a-date"
    with pytest.raises(ThesisIVOLDataError, match="invalid observation dates"):
        prepare_thesis_ivol_features(panel)
