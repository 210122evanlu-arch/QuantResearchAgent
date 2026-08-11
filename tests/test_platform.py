from datetime import date, datetime

import pytest
from pydantic import ValidationError

from agents.analysis_execution import AnalysisExecutionNode
from analysis_engines.router import AnalysisEngineRegistry, AnalysisEngineUnavailable
from examples.platform_routing_demo import run_platform_routing_demo
from graph.intent_router import intent_router_node, route_request
from graph.platform import WorkflowNotRegisteredError, WorkflowRegistry
from schemas.enums import AnalysisMethod, EvidenceStatus, TaskType
from schemas.platform import (
    AnalysisArtifact,
    AnalysisBundle,
    EvidenceRecord,
    ResearchFinding,
    ResearchRequest,
)
from tools.report_templates import resolve_report_template


def request(task_type: TaskType = TaskType.QUANT_RESEARCH) -> ResearchRequest:
    values = {
        "task_type": task_type,
        "question": "Test a generalised platform route",
        "as_of_date": date(2026, 8, 7),
    }
    if task_type in {TaskType.COMPANY_RESEARCH, TaskType.CORPORATE_ADVISORY}:
        values["companies"] = ["Fixture Company"]
    if task_type == TaskType.INDUSTRY_RESEARCH:
        values["industries"] = ["Fixture Industry"]
    return ResearchRequest.model_validate(values)


@pytest.mark.parametrize("task_type", list(TaskType))
def test_all_task_types_have_valid_routes_and_templates(task_type) -> None:
    selection = route_request(request(task_type))

    assert selection.task_type == task_type
    assert selection.analysis_methods
    assert resolve_report_template(selection).is_file()


def test_intent_router_node_preserves_question_for_legacy_nodes() -> None:
    routed = intent_router_node({"request": request().model_dump(mode="json")})

    assert routed["research_question"] == "Test a generalised platform route"
    assert routed["workflow_selection"].workflow_name == "quant_research"


def test_company_route_adds_dcf_only_when_requested() -> None:
    base = request(TaskType.COMPANY_RESEARCH)
    dcf_request = base.model_copy(update={"topics": ["valuation", "dcf"]})
    assert AnalysisMethod.DCF_VALUATION not in route_request(base).analysis_methods
    assert AnalysisMethod.DCF_VALUATION in route_request(dcf_request).analysis_methods


def test_scoped_requests_require_a_subject() -> None:
    with pytest.raises(ValidationError, match="require a company or security"):
        ResearchRequest(
            task_type=TaskType.COMPANY_RESEARCH,
            question="Analyse this company",
            as_of_date=date(2026, 8, 7),
        )

    with pytest.raises(ValidationError, match="requires at least one industry"):
        ResearchRequest(
            task_type=TaskType.INDUSTRY_RESEARCH,
            question="Analyse an industry",
            as_of_date=date(2026, 8, 7),
        )


def test_registry_dispatches_only_registered_workflows() -> None:
    registry = WorkflowRegistry()
    with pytest.raises(WorkflowNotRegisteredError):
        registry.dispatch(request())

    registry.register(TaskType.QUANT_RESEARCH, lambda value: {"q": value.question})
    result = registry.dispatch(request())
    assert result["workflow_result"] == {"q": "Test a generalised platform route"}


def test_verified_findings_are_evidence_backed() -> None:
    with pytest.raises(ValidationError, match="require at least one evidence_id"):
        ResearchFinding(
            finding_id="F1",
            statement="A verified claim",
            implication="A material implication",
            status=EvidenceStatus.VERIFIED,
            confidence=0.9,
        )

    finding = ResearchFinding(
        finding_id="F1",
        statement="A verified claim",
        implication="A material implication",
        evidence_ids=["E1"],
        status=EvidenceStatus.VERIFIED,
        confidence=0.9,
    )
    artifact = AnalysisArtifact(
        method=AnalysisMethod.REGRESSION,
        title="Regression",
        summary="Fixture analysis",
        findings=[finding],
    )
    with pytest.raises(ValidationError, match="unknown evidence_ids: E1"):
        AnalysisBundle(artifacts=[artifact])

    bundle = AnalysisBundle(
        artifacts=[artifact],
        evidence=[
            EvidenceRecord(
                evidence_id="E1",
                source_type="fixture",
                title="Fixture evidence",
                source_name="Test suite",
                retrieved_at=datetime(2026, 8, 7),
                summary="Evidence summary",
            )
        ],
    )
    assert bundle.artifacts[0].findings[0].evidence_ids == ["E1"]


def test_analysis_execution_is_method_routed_without_silent_fallback() -> None:
    registry = AnalysisEngineRegistry()
    with pytest.raises(AnalysisEngineUnavailable):
        registry.execute(AnalysisMethod.EVENT_STUDY, {})

    def fixture_engine(method):
        def execute(context):
            return AnalysisArtifact(
                method=method,
                title=method.value,
                summary=str(context["summary"]),
            )

        return execute

    registry.register(
        AnalysisMethod.REGRESSION,
        fixture_engine(AnalysisMethod.REGRESSION),
    )
    registry.register(
        AnalysisMethod.PORTFOLIO_BACKTEST,
        fixture_engine(AnalysisMethod.PORTFOLIO_BACKTEST),
    )
    node = AnalysisExecutionNode(registry)
    result = node(
        {
            "workflow_selection": route_request(request()),
            "analysis_context": {"summary": "Executed"},
        }
    )
    assert result["analysis_bundle"].artifacts[0].summary == "Executed"


def test_platform_demo_routes_every_service_line() -> None:
    results = run_platform_routing_demo()
    assert {result["request"].task_type for result in results} == set(TaskType)
