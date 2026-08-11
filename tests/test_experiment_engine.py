from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from agents.experiment import ExperimentDataMismatchError, create_experiment_node
from schemas.enums import DataFrequency
from schemas.model_design import ModelDesign
from tools.financial_data import LocalDataConfig, build_data_profile
from tools.statistics import (
    ExperimentConfig,
    run_experiment,
    run_fama_macbeth,
    run_ols,
)


def _model(
    *,
    estimator: str = "ols",
    standard_error_method: str = "HC3",
) -> ModelDesign:
    return ModelDesign.model_validate(
        {
            "model_name": estimator,
            "formula": "future_return ~ IVOL + size",
            "estimator": estimator,
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
                    "expected_sign": "negative",
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
            "standard_error_method": standard_error_method,
            "assumptions": ["Linear conditional relation"],
            "endogeneity_strategy": ["Lag predictors"],
            "limitations": [],
        }
    )


def _ols_frame() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    ivol = np.linspace(0.01, 0.10, 80)
    size = rng.normal(10, 1, 80)
    noise = rng.normal(0, 0.01, 80)
    returns = 0.02 - 0.8 * ivol + 0.01 * size + noise
    return pd.DataFrame({"future_return": returns, "IVOL": ivol, "size": size})


def test_ols_returns_computed_statistics_and_robustness() -> None:
    result = run_ols(_ols_frame(), _model(), ExperimentConfig())

    ivol = next(item for item in result.statistical_results if item.variable == "IVOL")
    assert result.estimator.value == "ols"
    assert result.sample_size == 80
    assert result.model_metrics.observations == 80
    assert ivol.coefficient == pytest.approx(-0.8, abs=0.08)
    assert ivol.standard_error is not None
    assert ivol.p_value is not None
    assert ivol.significant == (ivol.p_value < result.significance_level)
    assert len(result.robustness_checks) == 1
    assert result.parameters["covariance_type"] == "HC3"


def test_fama_macbeth_averages_cross_sectional_slopes() -> None:
    rng = np.random.default_rng(11)
    frames = []
    betas = [-0.60, -0.55, -0.50, -0.45, -0.40, -0.50]
    for period, beta in enumerate(betas, start=1):
        ivol = rng.uniform(0.01, 0.10, 24)
        size = rng.normal(10, 1, 24)
        noise = rng.normal(0, 0.002, 24)
        returns = 0.01 + beta * ivol + 0.005 * size + noise
        frames.append(
            pd.DataFrame(
                {
                    "date": pd.Timestamp(2023, period, 28),
                    "future_return": returns,
                    "IVOL": ivol,
                    "size": size,
                }
            )
        )
    frame = pd.concat(frames, ignore_index=True)

    result = run_fama_macbeth(
        frame,
        _model(estimator="fama_macbeth", standard_error_method="Newey-West"),
        ExperimentConfig(hac_maxlags=1),
        date_column="date",
    )

    ivol = next(item for item in result.statistical_results if item.variable == "IVOL")
    assert result.estimator.value == "fama_macbeth"
    assert result.parameters["periods"] == 6
    assert result.sample_size == 144
    assert ivol.coefficient == pytest.approx(np.mean(betas), abs=0.04)
    assert ivol.standard_error is not None
    assert result.robustness_checks[0].name.startswith("Fama-MacBeth")


def test_sequential_portfolio_sort_produces_25_cells_and_five_spreads() -> None:
    rows = []
    for month_number, month in enumerate(
        pd.date_range("2023-01-31", periods=8, freq="ME")
    ):
        for stock in range(50):
            turnover = float(stock + 1)
            ivol = float((stock * 7) % 50 + 1) / 1000
            rows.append(
                {
                    "date": month,
                    "future_return": 0.02
                    - ivol * (1 + turnover / 50)
                    + month_number / 10000,
                    "turnover": turnover,
                    "IVOL": ivol,
                }
            )
    frame = pd.DataFrame(rows)
    model = ModelDesign.model_validate(
        {
            "model_name": "Sequential portfolio sort",
            "formula": "future_return ~ turnover + IVOL",
            "estimator": "portfolio_sort",
            "dependent_variable": {
                "name": "future_return",
                "role": "dependent",
                "definition": "Next return",
            },
            "independent_variables": [
                {
                    "name": "turnover",
                    "role": "independent",
                    "definition": "Turnover",
                },
                {
                    "name": "IVOL",
                    "role": "independent",
                    "definition": "IVOL",
                },
            ],
            "control_variables": [],
            "fixed_effects": [],
            "standard_error_method": "Newey-West",
            "assumptions": ["Sequential sorts"],
            "endogeneity_strategy": [],
            "limitations": [],
        }
    )

    result = run_experiment(frame, model, ExperimentConfig(), date_column="date")

    assert result.estimator.value == "portfolio_sort"
    assert result.sample_size == 400
    assert len(result.portfolio_results) == 25
    assert len(result.statistical_results) == 5
    assert result.statistical_results[-1].coefficient < 0


def test_experiment_node_rejects_changed_data_file(tmp_path: Path) -> None:
    path = tmp_path / "experiment.csv"
    frame = _ols_frame()
    frame.insert(0, "stock_id", [f"S{i:03d}" for i in range(len(frame))])
    frame.insert(1, "date", "2024-01-31")
    frame.insert(2, "target_date", "2024-02-29")
    frame.to_csv(path, index=False)
    config = LocalDataConfig(
        path=path,
        date_column="date",
        target_date_column="target_date",
        entity_column="stock_id",
        frequency=DataFrequency.MONTHLY,
        universe="Synthetic test sample",
    )
    model = _model()
    profile = build_data_profile(config, model)
    frame.loc[0, "future_return"] = 99
    frame.to_csv(path, index=False)

    with pytest.raises(ExperimentDataMismatchError, match="changed"):
        create_experiment_node(config)({"model_design": model, "data_profile": profile})


def test_experiment_node_saves_reproducible_artifact(tmp_path: Path) -> None:
    path = tmp_path / "experiment.csv"
    frame = _ols_frame()
    frame.insert(0, "stock_id", [f"S{i:03d}" for i in range(len(frame))])
    frame.insert(1, "date", "2024-01-31")
    frame.insert(2, "target_date", "2024-02-29")
    frame.to_csv(path, index=False)
    config = LocalDataConfig(
        path=path,
        date_column="date",
        target_date_column="target_date",
        entity_column="stock_id",
        frequency=DataFrequency.MONTHLY,
        universe="Synthetic test sample",
    )
    model = _model()
    profile = build_data_profile(config, model)
    node = create_experiment_node(config, artifact_directory=tmp_path / "artifacts")

    first = node({"model_design": model, "data_profile": profile})["experiment_result"]
    second = node({"model_design": model, "data_profile": profile})["experiment_result"]

    assert first.artifact_path == second.artifact_path
    artifact = Path(first.artifact_path)
    assert artifact.is_file()
    content = artifact.read_text(encoding="utf-8")
    assert profile.dataset_fingerprint in content
    assert '"model_design"' in content
