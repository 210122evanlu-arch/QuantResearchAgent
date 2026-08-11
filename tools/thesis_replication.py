"""Locked empirical specifications derived from the IVOL thesis design."""

from __future__ import annotations

import pandas as pd

from schemas.experiment import ExperimentResult
from schemas.model_design import ModelDesign
from tools.statistics import ExperimentConfig, run_fama_macbeth, run_portfolio_sort


def _model(
    name: str,
    independent: list[str],
    controls: list[str],
) -> ModelDesign:
    regressors = [*independent, *controls]
    return ModelDesign.model_validate(
        {
            "model_name": name,
            "formula": "future_return ~ " + " + ".join(regressors),
            "estimator": "fama_macbeth",
            "dependent_variable": {
                "name": "future_return",
                "role": "dependent",
                "definition": "Next-month stock return",
            },
            "independent_variables": [
                {"name": variable, "role": "independent", "definition": variable}
                for variable in independent
            ],
            "control_variables": [
                {"name": variable, "role": "control", "definition": variable}
                for variable in controls
            ],
            "fixed_effects": [],
            "standard_error_method": "Newey-West",
            "assumptions": ["Stable monthly cross-sectional relation"],
            "endogeneity_strategy": ["Lag alignment and firm controls"],
            "limitations": [
                "Causal identification is not established by Fama-MacBeth regression."
            ],
        }
    )


def thesis_model_1() -> ModelDesign:
    """Baseline IVOL specification from the thesis."""
    return _model("Thesis Model 1", ["IVOL"], ["size", "bm"])


def thesis_model_3() -> ModelDesign:
    """Centered turnover-interaction specification from the thesis."""
    return _model(
        "Thesis Model 3",
        ["IVOL_c", "turnover_c", "ivol_turnover_c"],
        ["size", "bm"],
    )


def thesis_rank_model() -> ModelDesign:
    """Cross-sectional rank robustness specification."""
    return _model(
        "Thesis Rank Robustness",
        ["IVOL_rank_c", "turnover_rank_c", "interaction_rank_c"],
        ["size", "bm"],
    )


def thesis_portfolio_model() -> ModelDesign:
    """Sequential turnover-then-IVOL portfolio-sort specification."""
    model = _model("Thesis 5x5 Portfolio Sort", ["turnover", "IVOL"], [])
    payload = model.model_dump(mode="json")
    payload["estimator"] = "portfolio_sort"
    return ModelDesign.model_validate(payload)


def run_thesis_replication_suite(
    panel: pd.DataFrame,
    *,
    date_column: str = "date",
    experiment_config: ExperimentConfig | None = None,
) -> dict[str, ExperimentResult]:
    """Run locked baseline, interaction, rank, and microcap specifications."""
    config = experiment_config or ExperimentConfig(hac_maxlags=3)
    results = {
        "baseline": run_fama_macbeth(
            panel, thesis_model_1(), config, date_column=date_column
        ),
        "interaction": run_fama_macbeth(
            panel, thesis_model_3(), config, date_column=date_column
        ),
        "rank_robustness": run_fama_macbeth(
            panel, thesis_rank_model(), config, date_column=date_column
        ),
        "portfolio_sort": run_portfolio_sort(
            panel,
            thesis_portfolio_model(),
            config,
            date_column=date_column,
        ),
    }
    if "microcap" not in panel.columns:
        raise ValueError("Thesis microcap specification requires a microcap column")
    results["microcap"] = run_fama_macbeth(
        panel.loc[panel["microcap"].astype(bool)],
        thesis_model_3(),
        config,
        date_column=date_column,
    )
    return results
