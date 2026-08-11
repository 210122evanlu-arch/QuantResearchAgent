from copy import deepcopy
from datetime import date

import pytest

from agents.review import ReviewEvidenceError, create_review_node
from graph.router import review_decision_router, revision_target_router
from llm.fake import FakeStructuredLLM
from schemas.data_profile import DataProfile
from schemas.enums import ProblemType, ReviewDecision, RevisionTarget
from schemas.experiment import ExperimentResult
from schemas.model_design import ModelDesign
from schemas.review import ReviewResult
from tools.research_committee import ReviewPolicyConfig


def _model_payload() -> dict:
    return {
        "model_name": "OLS",
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
        "standard_error_method": "HC3",
        "assumptions": ["Linear conditional relation"],
        "endogeneity_strategy": ["Lag predictors"],
        "limitations": ["Residual confounding may remain"],
    }


def _data_payload() -> dict:
    return {
        "data_sources": ["fixture.csv"],
        "start_date": date(2020, 1, 1),
        "end_date": date(2024, 12, 31),
        "frequency": "monthly",
        "universe": "Synthetic sample",
        "sample_size": 120,
        "variables": ["future_return", "IVOL", "size"],
        "missing_rate": 0.0,
        "duplicate_rate": 0.0,
        "outlier_handling": "None",
        "look_ahead_bias_checked": True,
        "survivorship_bias_checked": True,
        "dataset_fingerprint": "sha256:verified",
    }


def _experiment_payload() -> dict:
    return {
        "method": "OLS with HC3 covariance",
        "estimator": "ols",
        "sample_size": 120,
        "model_metrics": {"observations": 120, "r_squared": 0.2},
        "statistical_results": [
            {
                "variable": "IVOL",
                "coefficient": -0.2,
                "standard_error": 0.05,
                "t_stat": -4.0,
                "p_value": 0.001,
                "confidence_interval": [-0.30, -0.10],
                "significant": True,
            },
            {
                "variable": "size",
                "coefficient": 0.01,
                "standard_error": 0.01,
                "t_stat": 1.0,
                "p_value": 0.32,
                "confidence_interval": [-0.01, 0.03],
                "significant": False,
            },
        ],
        "robustness_checks": [
            {
                "name": "Covariance sensitivity",
                "method": "Compare HC3 and classical inference",
                "result": "Stable",
                "passed": True,
            }
        ],
        "warnings": [],
        "conclusion": "IVOL is significant in the fixture.",
        "data_fingerprint": "sha256:verified",
    }


def _approved_advisory() -> dict:
    return {
        "strengths": ["Economic logic is documented"],
        "issues": [],
        "decision": "approved",
        "revision_target": None,
        "overall_assessment": "Reviewer found no additional blocking issue.",
    }


def _state(
    *,
    model: dict | None = None,
    data: dict | None = None,
    experiment: dict | None = None,
) -> dict:
    return {
        "model_design": ModelDesign.model_validate(model or _model_payload()),
        "data_profile": DataProfile.model_validate(data or _data_payload()),
        "experiment_result": ExperimentResult.model_validate(
            experiment or _experiment_payload()
        ),
    }


def _run(state: dict, advisory: dict | None = None) -> ReviewResult:
    node = create_review_node(
        FakeStructuredLLM({ReviewResult: advisory or _approved_advisory()}),
        ReviewPolicyConfig(),
    )
    return node(state)["review_result"]


def test_committee_approves_when_policy_and_reviewer_pass() -> None:
    result = _run(_state())

    assert result.decision == ReviewDecision.APPROVED
    assert result.revision_target is None
    assert not [issue for issue in result.issues if issue.blocking]
    assert any("fingerprint" in strength for strength in result.strengths)


def test_reviewer_cannot_approve_over_blocking_data_policy() -> None:
    data = deepcopy(_data_payload())
    data["survivorship_bias_checked"] = False

    result = _run(_state(data=data))

    assert result.decision == ReviewDecision.NEED_REVISION
    assert result.revision_target == RevisionTarget.DATA_PREPARATION
    issue = next(
        issue for issue in result.issues if issue.category == "survivorship_bias"
    )
    assert issue.rule_id == "DATA_SURVIVORSHIP_001"
    assert issue.evidence
    assert issue.origin.value == "policy"


def test_model_endogeneity_routes_to_model_design() -> None:
    model = deepcopy(_model_payload())
    model["limitations"] = ["Potential endogeneity remains"]
    model["endogeneity_strategy"] = []

    result = _run(_state(model=model))

    assert result.decision == ReviewDecision.NEED_REVISION
    assert result.revision_target == RevisionTarget.MODEL_DESIGN
    assert any(issue.rule_id == "MODEL_ENDOGENEITY_001" for issue in result.issues)


def test_failed_robustness_routes_to_experiment() -> None:
    experiment = deepcopy(_experiment_payload())
    experiment["robustness_checks"][0]["passed"] = False
    experiment["robustness_checks"][0]["result"] = "Unstable"

    result = _run(_state(experiment=experiment))

    assert result.decision == ReviewDecision.NEED_REVISION
    assert result.revision_target == RevisionTarget.EXPERIMENT
    assert any(issue.rule_id == "EXP_ROBUSTNESS_002" for issue in result.issues)


def test_critical_data_issue_has_priority_over_high_model_issue() -> None:
    model = deepcopy(_model_payload())
    model["limitations"] = []
    data = deepcopy(_data_payload())
    data["look_ahead_bias_checked"] = False

    result = _run(_state(model=model, data=data))

    assert result.revision_target == RevisionTarget.DATA_PREPARATION
    blocking_types = {issue.problem_type for issue in result.issues if issue.blocking}
    assert blocking_types == {ProblemType.DATA_ISSUE, ProblemType.MODEL_ISSUE}


def test_reviewer_can_add_evidence_grounded_high_model_issue() -> None:
    advisory = {
        "strengths": [],
        "issues": [
            {
                "category": "economic_logic",
                "problem_type": "model_issue",
                "severity": "high",
                "description": "The mechanism is not represented by a stated control.",
                "recommendation": "Clarify the mechanism and specification.",
                "evidence": ["model_design.control_variables"],
            }
        ],
        "decision": "need_revision",
        "revision_target": "model_design",
        "overall_assessment": "Reviewer requests a model revision.",
    }

    result = _run(_state(), advisory)

    assert result.decision == ReviewDecision.NEED_REVISION
    assert result.revision_target == RevisionTarget.MODEL_DESIGN
    issue = next(issue for issue in result.issues if issue.category == "economic_logic")
    assert issue.origin.value == "reviewer"
    assert issue.blocking is True


def test_reviewer_issue_without_artifact_evidence_is_rejected() -> None:
    advisory = {
        "strengths": [],
        "issues": [
            {
                "category": "unsupported_claim",
                "problem_type": "model_issue",
                "severity": "high",
                "description": "Unsupported reviewer claim.",
                "recommendation": "Revise the model.",
                "evidence": [],
            }
        ],
        "decision": "need_revision",
        "revision_target": "model_design",
        "overall_assessment": "Unsupported advisory.",
    }

    with pytest.raises(ReviewEvidenceError, match="no artifact evidence"):
        _run(_state(), advisory)


def test_reviewer_evidence_with_unknown_field_is_rejected() -> None:
    advisory = {
        "strengths": [],
        "issues": [
            {
                "category": "unknown_field",
                "problem_type": "data_issue",
                "severity": "high",
                "description": "References a field that does not exist.",
                "recommendation": "Do not accept unsupported evidence.",
                "evidence": ["data_profile.imaginary_score"],
            }
        ],
        "decision": "need_revision",
        "revision_target": "data_preparation",
        "overall_assessment": "Invalid evidence path.",
    }

    with pytest.raises(ReviewEvidenceError, match="unknown artifact fields"):
        _run(_state(), advisory)


def test_reviewer_evidence_accepts_colon_value_notation() -> None:
    advisory = {
        "strengths": [],
        "issues": [
            {
                "category": "outliers",
                "problem_type": "data_issue",
                "severity": "medium",
                "description": "Outlier treatment requires sensitivity analysis.",
                "recommendation": "Add winsorization sensitivity checks.",
                "evidence": ["data_profile.outlier_handling: no winsorization"],
                "blocking": False,
            }
        ],
        "decision": "approved",
        "revision_target": None,
        "overall_assessment": "Non-blocking reviewer concern.",
    }

    result = _run(_state(), advisory)

    assert any(issue.category == "outliers" for issue in result.issues)


def test_reviewer_evidence_expands_unambiguous_experiment_shorthand() -> None:
    advisory = {
        "strengths": [],
        "issues": [
            {
                "category": "fit",
                "problem_type": "experiment_issue",
                "severity": "medium",
                "description": "Model fit needs interpretation.",
                "recommendation": "Discuss adjusted fit.",
                "evidence": ["model_metrics.adjusted_r_squared = 0.03"],
                "blocking": False,
            }
        ],
        "decision": "approved",
        "revision_target": None,
        "overall_assessment": "Non-blocking concern.",
    }

    result = _run(_state(), advisory)
    issue = next(issue for issue in result.issues if issue.category == "fit")

    assert issue.evidence == [
        "experiment_result.model_metrics.adjusted_r_squared = 0.03"
    ]


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (RevisionTarget.MODEL_DESIGN, "model_design"),
        (RevisionTarget.DATA_PREPARATION, "data_preparation"),
        (RevisionTarget.EXPERIMENT, "experiment"),
    ],
)
def test_all_revision_targets_route_deterministically(target, expected) -> None:
    problem_by_target = {
        RevisionTarget.MODEL_DESIGN: "model_issue",
        RevisionTarget.DATA_PREPARATION: "data_issue",
        RevisionTarget.EXPERIMENT: "experiment_issue",
    }
    review = ReviewResult.model_validate(
        {
            "issues": [
                {
                    "category": "route_fixture",
                    "problem_type": problem_by_target[target],
                    "severity": "high",
                    "description": "Route fixture",
                    "recommendation": "Revise target",
                }
            ],
            "decision": "need_revision",
            "revision_target": target,
            "overall_assessment": "Route fixture",
        }
    )
    state = {"review_result": review, "revision_limit_reached": False}

    assert review_decision_router(state) == "revision"
    assert revision_target_router(state) == expected
