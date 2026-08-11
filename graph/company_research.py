"""End-to-end listed-company research graph with review loop protection."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.analysis_execution import AnalysisExecutionNode
from agents.company_research import (
    CompanyResearchReviewNode,
    CompanyResearchSynthesisNode,
)
from analysis_engines.router import AnalysisEngineRegistry
from graph.debate_gate import (
    DebateGateConfig,
    create_debate_gate_node,
    debate_gate_router,
)
from graph.intent_router import intent_router_node
from graph.router import revision_control_node
from schemas.enums import ReviewDecision, TaskType
from schemas.platform import ResearchRequest
from schemas.state import ResearchState
from tools.company_research_report import (
    render_company_research_report,
    save_company_research_report,
)

CompanyNode = Callable[[ResearchState], dict[str, Any]]
CompanyContextProvider = Callable[[ResearchRequest], Mapping[str, Any]]


def company_intake_node(state: dict[str, Any]) -> dict:
    request = state.get("request")
    if request is None:
        raise ValueError("company research requires a request")
    if not isinstance(request, ResearchRequest):
        request = ResearchRequest.model_validate(request)
    if request.task_type != TaskType.COMPANY_RESEARCH:
        raise ValueError(
            "company research workflow requires task_type=company_research"
        )
    return intent_router_node({"request": request})


def company_review_router(state: ResearchState) -> str:
    if state["company_research_review"].decision == ReviewDecision.APPROVED:
        return "approved"
    return "revision"


def company_revision_router(state: ResearchState) -> str:
    if state.get("revision_limit_reached", False):
        return "report"
    target = state["company_research_review"].revision_target
    if target is None:
        raise ValueError("company research revision is missing a target")
    return target.value


@dataclass(frozen=True)
class CompanyResearchReportNode:
    output_path: Path
    name: str = "company_report"

    def __call__(self, state: ResearchState) -> dict:
        content = render_company_research_report(
            state["company_research_report"],
            state["analysis_bundle"],
            state["company_research_review"],
            state.get("debate_result"),
        )
        path = save_company_research_report(content, self.output_path)
        return {"report_markdown_path": str(path), "current_stage": self.name}


@dataclass(frozen=True)
class CompanyResearchHandler:
    """Adapt the graph to the platform registry's request-only handler contract."""

    workflow: Any
    context_provider: CompanyContextProvider
    max_revisions: int = 2

    def __post_init__(self) -> None:
        if self.max_revisions < 0:
            raise ValueError("max_revisions must be non-negative")

    def __call__(self, request: ResearchRequest) -> Mapping[str, Any]:
        return self.workflow.invoke(
            {
                "request": request,
                "analysis_context": dict(self.context_provider(request)),
                "revision_count": 0,
                "max_revisions": self.max_revisions,
            }
        )


def _debate_not_configured(_state: ResearchState) -> dict:
    raise RuntimeError(
        "Debate Gate entered, but no debate workflow was injected into company research"
    )


def build_company_research_workflow(
    registry: AnalysisEngineRegistry,
    *,
    report_path: str | Path,
    debate_workflow: CompanyNode | None = None,
    gate_config: DebateGateConfig | None = None,
):
    """Compile intake, four-method analysis, debate gate, review, and reporting."""
    graph = StateGraph(ResearchState)
    graph.add_node("company_intake", company_intake_node)
    graph.add_node("company_analysis", AnalysisExecutionNode(registry))
    graph.add_node("debate_gate", create_debate_gate_node(gate_config))
    graph.add_node("debate", debate_workflow or _debate_not_configured)
    graph.add_node("company_synthesis", CompanyResearchSynthesisNode())
    graph.add_node("company_review", CompanyResearchReviewNode())
    graph.add_node("revision_control", revision_control_node)
    graph.add_node("company_report", CompanyResearchReportNode(Path(report_path)))

    graph.add_edge(START, "company_intake")
    graph.add_edge("company_intake", "company_analysis")
    graph.add_edge("company_analysis", "debate_gate")
    graph.add_conditional_edges(
        "debate_gate",
        debate_gate_router,
        {"debate": "debate", "skip": "company_synthesis"},
    )
    graph.add_edge("debate", "company_synthesis")
    graph.add_edge("company_synthesis", "company_review")
    graph.add_conditional_edges(
        "company_review",
        company_review_router,
        {"approved": "company_report", "revision": "revision_control"},
    )
    graph.add_conditional_edges(
        "revision_control",
        company_revision_router,
        {
            "company_analysis": "company_analysis",
            "company_synthesis": "company_synthesis",
            "report": "company_report",
        },
    )
    graph.add_edge("company_report", END)
    return graph.compile()
