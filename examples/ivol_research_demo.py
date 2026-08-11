"""Offline IVOL research workflow using all seven nodes and a Fake LLM."""

from copy import deepcopy
from pathlib import Path

from literature.protocol import StaticLiteratureRetriever
from llm.fake import FakeStructuredLLM
from production import build_production_workflow
from schemas.enums import DataFrequency
from schemas.literature import RetrievedPaper
from schemas.model_design import ModelDesign
from schemas.research_analysis import ResearchAnalysis
from schemas.research_plan import ResearchPlan
from schemas.review import ReviewResult
from tools.financial_data import LocalDataConfig
from tools.research_committee import ReviewPolicyConfig


def _fake_responses() -> dict:
    """Return deterministic fixtures; none of the citations or results are real."""
    hypothesis = {
        "hypothesis_id": "H1",
        "statement": "IVOL negatively predicts future stock returns",
        "dependent_variable": "future_return",
        "independent_variable": "IVOL",
        "expected_direction": "negative",
        "rationale": "Offline fixture used to verify workflow behavior.",
    }

    initial_model = {
        "model_name": "OLS Regression - Initial Fixture",
        "formula": "future_return ~ IVOL",
        "estimator": "ols",
        "dependent_variable": {
            "name": "future_return",
            "role": "dependent",
            "definition": "Next-month stock return",
        },
        "independent_variables": [
            {
                "name": "IVOL",
                "role": "independent",
                "definition": "Idiosyncratic volatility",
                "calculation": "Residual volatility from a factor-model fixture",
                "expected_sign": "negative",
            }
        ],
        "control_variables": [],
        "fixed_effects": [],
        "standard_error_method": "Newey-West",
        "assumptions": ["Linear conditional relation"],
        "endogeneity_strategy": [],
        "limitations": ["Size is not controlled in the initial fixture"],
    }
    revised_model = deepcopy(initial_model)
    revised_model.update(
        {
            "model_name": "OLS Regression - Revised Fixture",
            "formula": "future_return ~ IVOL + size",
            "control_variables": [
                {
                    "name": "size",
                    "role": "control",
                    "definition": "Log market capitalization",
                    "expected_sign": "uncertain",
                }
            ],
            "limitations": ["Offline synthetic fixture; not investment evidence"],
        }
    )

    return {
        ResearchPlan: {
            "research_question": "Does IVOL predict future stock returns?",
            "research_objective": "Verify the seven-node workflow with offline fixtures.",
            "research_type": "panel",
            "hypotheses": [hypothesis],
            "methodology": "OLS regression fixture",
            "required_data": ["future returns", "IVOL", "size"],
            "evaluation_metrics": ["coefficient", "t-stat", "p-value", "r-squared"],
        },
        ResearchAnalysis: {
            "related_theories": ["Offline fixture theory"],
            "existing_models": ["OLS fixture"],
            "key_papers": [
                {
                    "title": "Offline Fixture Paper - Not a Real Citation",
                    "authors": ["Fixture Author"],
                    "year": 2020,
                    "source": "Local test fixture",
                    "key_finding": "Used only to test schema and graph wiring",
                    "relevance": "No research inference may be drawn",
                    "doi_or_url": "https://example.invalid/offline-fixture",
                }
            ],
            "theoretical_mechanism": "Synthetic mechanism for workflow testing.",
            "research_gap": "This demo deliberately uses an offline literature fixture.",
            "refined_hypotheses": [hypothesis],
        },
        ModelDesign: [initial_model, revised_model],
        ReviewResult: [
            {
                "strengths": ["Initial experiment is structurally valid"],
                "issues": [
                    {
                        "category": "omitted_variable",
                        "problem_type": "model_issue",
                        "severity": "high",
                        "description": "The initial fixture omits the size control.",
                        "recommendation": "Add size and rerun downstream stages.",
                        "evidence": ["model_design.control_variables"],
                    }
                ],
                "decision": "need_revision",
                "revision_target": "model_design",
                "overall_assessment": "Return to Model Design.",
            },
            {
                "strengths": ["Requested size control is included"],
                "issues": [],
                "decision": "approved",
                "revision_target": None,
                "overall_assessment": "Approved as an offline workflow fixture.",
            },
        ],
    }


def build_ivol_fake_workflow(report_path: Path | None = None):
    """Build the real seven-node graph with deterministic Fake LLM-backed nodes."""
    llm = FakeStructuredLLM(_fake_responses())
    literature_retriever = StaticLiteratureRetriever(
        [
            RetrievedPaper(
                title="Offline Fixture Paper - Not a Real Citation",
                authors=["Fixture Author"],
                year=2020,
                journal="Local test fixture",
                issn="0000-0000",
                url="https://example.invalid/offline-fixture",
                abstract="Synthetic metadata used only to test graph wiring.",
                metadata_source="offline_fixture",
                journal_whitelisted=False,
            )
        ]
    )
    data_config = LocalDataConfig(
        path=Path(__file__).parent / "data" / "ivol_fixture.csv",
        date_column="date",
        target_date_column="target_date",
        entity_column="stock_id",
        frequency=DataFrequency.MONTHLY,
        universe="Synthetic two-stock fixture",
        outlier_handling="None; offline fixture",
        survivorship_policy="Fixture includes its complete declared universe.",
    )
    workflow = build_production_workflow(
        data_config,
        report_path=report_path,
        llm=llm,
        literature_retriever=literature_retriever,
        review_policy=ReviewPolicyConfig(
            minimum_observations_per_parameter=3,
            failed_robustness_requires_revision=False,
        ),
    )
    return workflow, llm


def run_ivol_fake_demo(report_path: Path | None = None):
    """Execute a model-revision loop and return final state plus call trace."""
    workflow, llm = build_ivol_fake_workflow(report_path)
    result = workflow.invoke(
        {
            "research_question": "Does IVOL predict future stock returns?",
            "revision_count": 0,
            "max_revisions": 3,
            "errors": [],
        }
    )
    return result, llm


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    report_path = project_root / "reports" / "ivol_research_demo.md"
    final_state, fake_llm = run_ivol_fake_demo(report_path)
    call_path = " -> ".join(call.node_name for call in fake_llm.calls)

    print("Seven-node Fake LLM workflow: passed")
    print("Fake LLM calls (Data, Experiment, and Report are code-based):", call_path)
    print("Revision count:", final_state["revision_count"])
    print("Review decision:", final_state["review_result"].decision.value)
    print("Report title:", final_state["final_report"].title)
    print("Markdown report:", final_state["report_markdown_path"])
