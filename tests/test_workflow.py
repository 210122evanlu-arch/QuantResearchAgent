from datetime import date

import pytest

from agents.report import create_report_node
from graph.workflow import WorkflowNodes, build_workflow
from schemas.common import PaperReference, ResearchHypothesis, VariableDefinition
from schemas.data_profile import DataProfile
from schemas.enums import (
    DataFrequency,
    ExpectedDirection,
    IssueSeverity,
    ProblemType,
    ResearchType,
    ReviewDecision,
    RevisionTarget,
    VariableRole,
)
from schemas.experiment import ExperimentResult, ModelMetrics, StatisticalResult
from schemas.model_design import ModelDesign
from schemas.research_analysis import ResearchAnalysis
from schemas.research_plan import ResearchPlan
from schemas.review import ReviewIssue, ReviewResult


@pytest.fixture
def hypothesis() -> ResearchHypothesis:
    return ResearchHypothesis(
        hypothesis_id="H1",
        statement="IVOL negatively predicts future returns",
        dependent_variable="future_return",
        independent_variable="IVOL",
        expected_direction=ExpectedDirection.NEGATIVE,
        rationale="Risk and mispricing channels imply a negative relation.",
    )


def make_fake_nodes(
    hypothesis: ResearchHypothesis,
    *,
    always_revise: bool = False,
) -> WorkflowNodes:
    def research_manager(state):
        return {
            "research_plan": ResearchPlan(
                research_question=state["research_question"],
                research_objective="Test the IVOL-return relation.",
                research_type=ResearchType.PANEL,
                hypotheses=[hypothesis],
                methodology="Fama-MacBeth regression",
                required_data=["returns", "factor returns"],
                evaluation_metrics=["coefficient", "t-stat", "r-squared"],
            )
        }

    def research_analysis(state):
        return {
            "research_analysis": ResearchAnalysis(
                related_theories=["mispricing"],
                existing_models=["Fama-French"],
                key_papers=[
                    PaperReference(
                        title="Verified fixture paper",
                        authors=["Test Author"],
                        year=2020,
                        source="Test fixture",
                        key_finding="Fixture finding",
                        relevance="Used only for an offline graph test",
                    )
                ],
                theoretical_mechanism="Fixture mechanism",
                research_gap="Fixture research gap",
                refined_hypotheses=[hypothesis],
            )
        }

    def model_design(state):
        return {
            "model_design": ModelDesign(
                model_name="Fama-MacBeth Regression",
                formula="future_return ~ IVOL + size",
                estimator="fama_macbeth",
                dependent_variable=VariableDefinition(
                    name="future_return",
                    role=VariableRole.DEPENDENT,
                    definition="Next-period stock return",
                ),
                independent_variables=[
                    VariableDefinition(
                        name="IVOL",
                        role=VariableRole.INDEPENDENT,
                        definition="Idiosyncratic volatility",
                        expected_sign=ExpectedDirection.NEGATIVE,
                    )
                ],
                control_variables=[
                    VariableDefinition(
                        name="size",
                        role=VariableRole.CONTROL,
                        definition="Log market capitalization",
                    )
                ],
                fixed_effects=[],
                standard_error_method="Newey-West",
                assumptions=["Linear conditional relation"],
                endogeneity_strategy=[],
                limitations=["Fixture model"],
            )
        }

    def data_preparation(state):
        return {
            "data_profile": DataProfile(
                data_sources=["Synthetic test fixture"],
                start_date=date(2020, 1, 1),
                end_date=date(2024, 12, 31),
                frequency=DataFrequency.MONTHLY,
                universe="Synthetic A-share sample",
                sample_size=1000,
                variables=["future_return", "IVOL", "size"],
                missing_rate=0.0,
                duplicate_rate=0.0,
                outlier_handling="None for fixture",
                look_ahead_bias_checked=True,
                survivorship_bias_checked=True,
                dataset_fingerprint="sha256:workflow-fixture",
            )
        }

    def experiment(state):
        return {
            "experiment_result": ExperimentResult(
                method="Fama-MacBeth Regression",
                estimator="fama_macbeth",
                sample_size=1000,
                model_metrics=ModelMetrics(observations=1000, r_squared=0.18),
                statistical_results=[
                    StatisticalResult(
                        variable="IVOL",
                        coefficient=-0.25,
                        t_stat=-2.5,
                        p_value=0.01,
                        significant=True,
                    )
                ],
                robustness_checks=[],
                warnings=[],
                conclusion="Fixture experiment completed.",
                data_fingerprint="sha256:workflow-fixture",
            )
        }

    def review(state):
        should_revise = always_revise or state.get("revision_count", 0) == 0
        if should_revise:
            return {
                "review_result": ReviewResult(
                    issues=[
                        ReviewIssue(
                            category="model_specification",
                            problem_type=ProblemType.MODEL_ISSUE,
                            severity=IssueSeverity.HIGH,
                            description="Fixture requests a model revision.",
                            recommendation="Rerun the model fixture.",
                        )
                    ],
                    decision=ReviewDecision.NEED_REVISION,
                    revision_target=RevisionTarget.MODEL_DESIGN,
                    overall_assessment="Revision required.",
                )
            }

        return {
            "review_result": ReviewResult(
                decision=ReviewDecision.APPROVED,
                overall_assessment="Approved after fixture revision.",
            )
        }

    def report(state):
        return create_report_node()(state)

    return WorkflowNodes(
        research_manager=research_manager,
        research_analysis=research_analysis,
        model_design=model_design,
        data_preparation=data_preparation,
        experiment=experiment,
        review=review,
        report=report,
    )


def test_workflow_approves_after_one_model_revision(hypothesis) -> None:
    workflow = build_workflow(make_fake_nodes(hypothesis))
    result = workflow.invoke(
        {
            "research_question": "IVOL是否影响股票未来收益？",
            "revision_count": 0,
            "max_revisions": 3,
            "errors": [],
        }
    )

    assert result["revision_count"] == 1
    assert result["review_result"].decision == ReviewDecision.APPROVED
    assert result["final_report"].review_decision == ReviewDecision.APPROVED


def test_workflow_forces_report_after_revision_limit(hypothesis) -> None:
    workflow = build_workflow(make_fake_nodes(hypothesis, always_revise=True))
    result = workflow.invoke(
        {
            "research_question": "IVOL是否影响股票未来收益？",
            "revision_count": 0,
            "max_revisions": 1,
            "errors": [],
        }
    )

    assert result["revision_count"] == 1
    assert result["revision_limit_reached"] is True
    assert result["final_report"].review_decision == ReviewDecision.NEED_REVISION
    assert any(
        "approval was not obtained" in risk.casefold()
        for risk in result["final_report"].risk_disclosures
    )
