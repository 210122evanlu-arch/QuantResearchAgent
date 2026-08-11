"""End-to-end industry research graph with committee revision control."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.analysis_execution import AnalysisExecutionNode
from agents.industry_research import (
    IndustryResearchReviewNode,
    IndustryResearchSynthesisNode,
)
from analysis_engines.router import AnalysisEngineRegistry
from graph.intent_router import intent_router_node
from graph.router import revision_control_node
from schemas.enums import ReviewDecision, TaskType
from schemas.platform import ResearchRequest
from schemas.state import ResearchState
from tools.industry_research_report import (
    render_industry_research_report,
    save_industry_research_report,
)

IndustryContextProvider = Callable[[ResearchRequest], Mapping[str, Any]]


def industry_intake_node(state: dict[str, Any]) -> dict:
    request = state.get("request")
    if request is None:
        raise ValueError("industry research requires a request")
    if not isinstance(request, ResearchRequest):
        request = ResearchRequest.model_validate(request)
    if request.task_type != TaskType.INDUSTRY_RESEARCH:
        raise ValueError(
            "industry research workflow requires task_type=industry_research"
        )
    return intent_router_node({"request": request})


def industry_review_router(state: ResearchState) -> str:
    if state["industry_research_review"].decision == ReviewDecision.APPROVED:
        return "approved"
    return "revision"


def industry_revision_router(state: ResearchState) -> str:
    if state.get("revision_limit_reached", False):
        return "report"
    target = state["industry_research_review"].revision_target
    if target is None:
        raise ValueError("industry research revision is missing a target")
    return target.value


@dataclass(frozen=True)
class IndustryResearchReportNode:
    output_path: Path
    name: str = "industry_report"

    def __call__(self, state: ResearchState) -> dict:
        content = render_industry_research_report(
            state["industry_research_report"],
            state["analysis_bundle"],
            state["industry_research_review"],
        )
        path = save_industry_research_report(content, self.output_path)
        return {"report_markdown_path": str(path), "current_stage": self.name}


@dataclass(frozen=True)
class IndustryResearchHandler:
    workflow: Any
    context_provider: IndustryContextProvider
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


def build_industry_research_workflow(
    registry: AnalysisEngineRegistry,
    *,
    report_path: str | Path,
):
    """Compile intake, analysis, synthesis, review loop, and reporting."""
    graph = StateGraph(ResearchState)
    graph.add_node("industry_intake", industry_intake_node)
    graph.add_node("industry_analysis", AnalysisExecutionNode(registry))
    graph.add_node("industry_synthesis", IndustryResearchSynthesisNode())
    graph.add_node("industry_review", IndustryResearchReviewNode())
    graph.add_node("revision_control", revision_control_node)
    graph.add_node("industry_report", IndustryResearchReportNode(Path(report_path)))

    graph.add_edge(START, "industry_intake")
    graph.add_edge("industry_intake", "industry_analysis")
    graph.add_edge("industry_analysis", "industry_synthesis")
    graph.add_edge("industry_synthesis", "industry_review")
    graph.add_conditional_edges(
        "industry_review",
        industry_review_router,
        {"approved": "industry_report", "revision": "revision_control"},
    )
    graph.add_conditional_edges(
        "revision_control",
        industry_revision_router,
        {
            "industry_analysis": "industry_analysis",
            "industry_synthesis": "industry_synthesis",
            "report": "industry_report",
        },
    )
    graph.add_edge("industry_report", END)
    return graph.compile()
