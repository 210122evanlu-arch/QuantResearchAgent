from datetime import date

import pytest
from pydantic import ValidationError

from graph.router import (
    review_decision_router,
    revision_control_node,
    revision_target_router,
)
from schemas.data_profile import DataProfile
from schemas.enums import (
    DataFrequency,
    IssueSeverity,
    ProblemType,
    ReviewDecision,
    RevisionTarget,
)
from schemas.experiment import ExperimentResult, ModelMetrics, StatisticalResult
from schemas.review import ReviewIssue, ReviewResult


def test_data_profile_rejects_invalid_rates() -> None:
    with pytest.raises(ValidationError):
        DataProfile(
            data_sources=["A-share market data"],
            start_date=date(2010, 1, 1),
            end_date=date(2025, 12, 31),
            frequency=DataFrequency.MONTHLY,
            universe="A-share common stocks",
            sample_size=1000,
            variables=["return", "IVOL"],
            missing_rate=1.1,
            duplicate_rate=0.0,
            outlier_handling="Winsorize at 1% and 99%",
            look_ahead_bias_checked=True,
            survivorship_bias_checked=True,
        )


def test_experiment_rejects_inconsistent_significance() -> None:
    with pytest.raises(ValidationError):
        ExperimentResult(
            method="Fama-MacBeth Regression",
            sample_size=1000,
            model_metrics=ModelMetrics(observations=1000),
            statistical_results=[
                StatisticalResult(
                    variable="IVOL",
                    coefficient=-0.25,
                    p_value=0.20,
                    significant=True,
                )
            ],
            robustness_checks=[],
            warnings=[],
            conclusion="Placeholder conclusion",
        )


def test_review_routers_use_decision_and_revision_target() -> None:
    review = ReviewResult(
        issues=[
            ReviewIssue(
                category="omitted_variable",
                problem_type=ProblemType.MODEL_ISSUE,
                severity=IssueSeverity.HIGH,
                description="Size factor is not controlled.",
                recommendation="Add Size and BM controls.",
            )
        ],
        decision=ReviewDecision.NEED_REVISION,
        revision_target=RevisionTarget.MODEL_DESIGN,
        overall_assessment="Model revision is required.",
    )

    state = {
        "review_result": review,
        "revision_count": 0,
        "max_revisions": 3,
    }

    assert review_decision_router(state) == "revision"

    state.update(revision_control_node(state))
    assert state["revision_count"] == 1
    assert revision_target_router(state) == "model_design"


def test_revision_limit_forces_report() -> None:
    review = ReviewResult(
        issues=[
            ReviewIssue(
                category="robustness",
                problem_type=ProblemType.EXPERIMENT_ISSUE,
                severity=IssueSeverity.HIGH,
                description="Robustness checks are incomplete.",
                recommendation="Run an alternative specification.",
            )
        ],
        decision=ReviewDecision.NEED_REVISION,
        revision_target=RevisionTarget.EXPERIMENT,
        overall_assessment="Experiment revision is required.",
    )
    state = {
        "review_result": review,
        "revision_count": 3,
        "max_revisions": 3,
    }

    state.update(revision_control_node(state))
    assert state["revision_limit_reached"] is True
    assert revision_target_router(state) == "report"
