from pathlib import Path

import pandas as pd

from agents.data_preparation import create_data_preparation_node
from agents.experiment import create_experiment_node
from schemas.enums import DataFrequency
from schemas.model_design import ModelDesign
from schemas.research_plan import ResearchPlan
from schemas.review import ReviewResult
from tools.financial_data import LocalDataConfig


def _model() -> ModelDesign:
    return ModelDesign.model_validate(
        {
            "model_name": "IVOL OLS",
            "formula": "future_return ~ IVOL + size",
            "estimator": "ols",
            "dependent_variable": {
                "name": "future_return",
                "role": "dependent",
                "definition": "Future return",
            },
            "independent_variables": [
                {
                    "name": "IVOL",
                    "role": "independent",
                    "definition": "Idiosyncratic volatility",
                }
            ],
            "control_variables": [
                {"name": "size", "role": "control", "definition": "Log size"}
            ],
            "fixed_effects": [],
            "standard_error_method": "HC3",
            "assumptions": ["Linear relation"],
            "endogeneity_strategy": [],
            "limitations": [],
        }
    )


def _plan() -> ResearchPlan:
    return ResearchPlan.model_validate(
        {
            "research_question": "Does IVOL predict returns?",
            "research_objective": "Test IVOL.",
            "research_type": "panel",
            "hypotheses": [
                {
                    "hypothesis_id": "H1",
                    "statement": "IVOL predicts returns",
                    "dependent_variable": "future_return",
                    "independent_variable": "IVOL",
                    "expected_direction": "negative",
                    "rationale": "Mispricing",
                }
            ],
            "methodology": "OLS",
            "required_data": ["returns"],
            "evaluation_metrics": ["coefficient"],
        }
    )


def _config(path: Path, universe: str) -> LocalDataConfig:
    return LocalDataConfig(
        path=path,
        date_column="date",
        target_date_column="target_date",
        entity_column="stock_id",
        frequency=DataFrequency.MONTHLY,
        universe=universe,
        survivorship_policy="Declared test universe.",
    )


def _write(path: Path, rows: int) -> None:
    pd.DataFrame(
        {
            "stock_id": [f"S{i}" for i in range(rows)],
            "date": ["2024-01-31"] * rows,
            "target_date": ["2024-02-29"] * rows,
            "future_return": [i / 100 for i in range(rows)],
            "IVOL": [0.01 + i / 1000 for i in range(rows)],
            "size": [10.0 + i * i for i in range(rows)],
        }
    ).to_parquet(path, index=False)


def test_data_revision_switches_profile_and_experiment_to_larger_file(tmp_path) -> None:
    initial_path = tmp_path / "initial.parquet"
    expanded_path = tmp_path / "expanded.parquet"
    _write(initial_path, 6)
    _write(expanded_path, 12)
    initial = _config(initial_path, "initial")
    expanded = _config(expanded_path, "expanded")
    data_node = create_data_preparation_node(initial, (expanded,))
    experiment_node = create_experiment_node(initial, revision_data_configs=(expanded,))
    state = {
        "research_plan": _plan(),
        "model_design": _model(),
        "review_result": ReviewResult.model_validate(
            {
                "issues": [
                    {
                        "category": "sample",
                        "problem_type": "data_issue",
                        "severity": "high",
                        "description": "Expand the sample.",
                        "recommendation": "Use the staged revision dataset.",
                    }
                ],
                "decision": "need_revision",
                "revision_target": "data_preparation",
                "overall_assessment": "Revision required.",
            }
        ),
        "active_data_revision_index": 0,
    }

    data_update = data_node(state)
    state.update(data_update)
    experiment_update = experiment_node(state)

    assert data_update["active_data_revision_index"] == 1
    assert data_update["data_profile"].sample_size == 12
    assert experiment_update["experiment_result"].sample_size == 12
