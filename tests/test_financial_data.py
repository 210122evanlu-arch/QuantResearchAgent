from pathlib import Path

import pandas as pd
import pytest

from schemas.enums import DataFrequency
from schemas.model_design import ModelDesign
from tools.financial_data import (
    LocalDataConfig,
    LookAheadBiasError,
    MissingModelVariablesError,
    build_data_profile,
    load_financial_data,
)


def _model() -> ModelDesign:
    return ModelDesign.model_validate(
        {
            "model_name": "Panel regression",
            "formula": "future_return ~ IVOL + size",
            "estimator": "ols",
            "dependent_variable": {
                "name": "future_return",
                "role": "dependent",
                "definition": "Next-period return",
            },
            "independent_variables": [
                {
                    "name": "IVOL",
                    "role": "independent",
                    "definition": "Idiosyncratic volatility",
                }
            ],
            "control_variables": [
                {
                    "name": "size",
                    "role": "control",
                    "definition": "Log market capitalization",
                }
            ],
            "fixed_effects": [],
            "standard_error_method": "robust",
            "assumptions": ["Linear relation"],
            "endogeneity_strategy": [],
            "limitations": [],
        }
    )


def _config(path: Path) -> LocalDataConfig:
    return LocalDataConfig(
        path=path,
        date_column="date",
        target_date_column="target_date",
        entity_column="stock_id",
        frequency=DataFrequency.MONTHLY,
        universe="Test stocks",
        outlier_handling="None",
        survivorship_policy="Includes delisted securities in the declared sample.",
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "stock_id": ["A", "A"],
            "date": ["2024-01-31", "2024-02-29"],
            "target_date": ["2024-02-29", "2024-03-31"],
            "future_return": [0.01, -0.02],
            "IVOL": [0.03, None],
            "size": [10.0, 10.1],
        }
    )


def test_profile_is_computed_from_csv(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    _frame().to_csv(path, index=False)

    profile = build_data_profile(_config(path), _model())

    assert profile.sample_size == 2
    assert profile.start_date.isoformat() == "2024-01-31"
    assert profile.end_date.isoformat() == "2024-02-29"
    assert profile.column_missing_rates["IVOL"] == 0.5
    assert profile.missing_rate == pytest.approx(1 / 6)
    assert profile.duplicate_rate == 0.0
    assert profile.look_ahead_bias_checked is True
    assert profile.survivorship_bias_checked is True
    assert profile.dataset_fingerprint.startswith("sha256:")


def test_missing_model_variable_stops_preparation(tmp_path: Path) -> None:
    path = tmp_path / "missing.csv"
    _frame().drop(columns=["size"]).to_csv(path, index=False)

    with pytest.raises(MissingModelVariablesError, match="size"):
        build_data_profile(_config(path), _model())


def test_non_future_target_date_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "leakage.csv"
    frame = _frame()
    frame.loc[0, "target_date"] = frame.loc[0, "date"]
    frame.to_csv(path, index=False)

    with pytest.raises(LookAheadBiasError, match="strictly later"):
        build_data_profile(_config(path), _model())


def test_duplicate_rate_uses_entity_date_key(tmp_path: Path) -> None:
    path = tmp_path / "duplicates.csv"
    frame = _frame()
    frame.loc[1, "date"] = frame.loc[0, "date"]
    frame.loc[1, "target_date"] = frame.loc[0, "target_date"]
    frame.to_csv(path, index=False)

    profile = build_data_profile(_config(path), _model())

    assert profile.duplicate_rate == 0.5


def test_missing_entity_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "missing-key.csv"
    frame = _frame()
    frame.loc[0, "stock_id"] = None
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="key columns"):
        build_data_profile(_config(path), _model())


def test_parquet_loader_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "sample.parquet"
    frame = _frame()
    frame.to_parquet(path, index=False)

    loaded = load_financial_data(path)

    assert list(loaded.columns) == list(frame.columns)
    assert len(loaded) == len(frame)
