from pathlib import Path

import pytest

from agents.base import NodeInputError
from agents.data_preparation import create_data_preparation_node
from agents.experiment import create_experiment_node
from agents.model_design import create_model_design_node
from agents.report import create_report_node
from agents.research_analysis import create_research_analysis_node
from agents.research_manager import create_research_manager_node
from agents.review import create_review_node
from literature.protocol import StaticLiteratureRetriever
from llm.fake import FakeStructuredLLM
from schemas.data_profile import DataProfile
from schemas.enums import DataFrequency, ExpectedDirection, ResearchType
from schemas.experiment import ExperimentResult
from schemas.model_design import ModelDesign
from schemas.report import FinalReport
from schemas.research_analysis import ResearchAnalysis
from schemas.research_plan import ResearchPlan
from schemas.review import ReviewResult
from tools.financial_data import LocalDataConfig

_UNUSED_DATA_CONFIG = LocalDataConfig(
    path=Path("unused.csv"),
    date_column="date",
    target_date_column="target_date",
    frequency=DataFrequency.MONTHLY,
    universe="test",
)


@pytest.mark.parametrize(
    ("factory", "schema", "output_key", "input_keys"),
    [
        (
            create_research_manager_node,
            ResearchPlan,
            "research_plan",
            ("research_question",),
        ),
        (
            lambda llm: create_research_analysis_node(
                llm, StaticLiteratureRetriever([])
            ),
            ResearchAnalysis,
            "research_analysis",
            ("research_plan",),
        ),
        (
            create_model_design_node,
            ModelDesign,
            "model_design",
            ("research_analysis",),
        ),
        (
            lambda _llm: create_data_preparation_node(_UNUSED_DATA_CONFIG),
            DataProfile,
            "data_profile",
            ("research_plan", "model_design"),
        ),
        (
            lambda _llm: create_experiment_node(_UNUSED_DATA_CONFIG),
            ExperimentResult,
            "experiment_result",
            ("model_design", "data_profile"),
        ),
        (
            create_review_node,
            ReviewResult,
            "review_result",
            ("model_design", "data_profile", "experiment_result"),
        ),
        (
            lambda _llm: create_report_node(),
            FinalReport,
            "final_report",
            (
                "research_plan",
                "research_analysis",
                "model_design",
                "data_profile",
                "experiment_result",
                "review_result",
            ),
        ),
    ],
)
def test_all_node_factories_expose_declared_contract(
    factory, schema, output_key, input_keys
) -> None:
    node = factory(FakeStructuredLLM({}))

    assert node.output_schema is schema
    assert node.output_key == output_key
    assert node.input_keys == input_keys


def test_research_manager_node_returns_validated_schema() -> None:
    llm = FakeStructuredLLM(
        {
            ResearchPlan: {
                "research_question": "Does IVOL predict future returns?",
                "research_objective": "Test the IVOL-return relation.",
                "research_type": ResearchType.PANEL,
                "hypotheses": [
                    {
                        "hypothesis_id": "H1",
                        "statement": "IVOL negatively predicts future returns",
                        "dependent_variable": "future_return",
                        "independent_variable": "IVOL",
                        "expected_direction": ExpectedDirection.NEGATIVE,
                        "rationale": "Test rationale",
                    }
                ],
                "methodology": "Fama-MacBeth regression",
                "required_data": ["returns", "factor returns"],
                "evaluation_metrics": ["coefficient", "t-stat"],
            }
        }
    )
    node = create_research_manager_node(llm)

    result = node({"research_question": "Does IVOL predict future returns?"})

    assert isinstance(result["research_plan"], ResearchPlan)
    assert result["current_stage"] == "research_manager"
    assert "Does IVOL" in llm.calls[0].user_prompt


def test_structured_node_rejects_missing_state_input() -> None:
    node = create_research_manager_node(FakeStructuredLLM({}))

    with pytest.raises(NodeInputError, match="research_question"):
        node({})
