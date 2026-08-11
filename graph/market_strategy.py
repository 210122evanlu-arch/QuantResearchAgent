"""End-to-end market strategy graph with committee revision control."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.analysis_execution import AnalysisExecutionNode
from agents.market_strategy import MarketStrategyReviewNode, MarketStrategySynthesisNode
from analysis_engines.router import AnalysisEngineRegistry
from graph.intent_router import intent_router_node
from graph.router import revision_control_node
from schemas.enums import ReviewDecision, TaskType
from schemas.platform import ResearchRequest
from schemas.state import ResearchState
from tools.market_strategy_report import (
    render_market_strategy_report,
    save_market_strategy_report,
)

MarketContextProvider = Callable[[ResearchRequest], Mapping[str, Any]]


def market_strategy_intake_node(state: dict[str, Any]) -> dict:
    request = state.get("request")
    if request is None:
        raise ValueError("market strategy requires a request")
    if not isinstance(request, ResearchRequest):
        request = ResearchRequest.model_validate(request)
    if request.task_type != TaskType.MARKET_STRATEGY:
        raise ValueError("market strategy workflow requires task_type=market_strategy")
    return intent_router_node({"request": request})


def market_strategy_review_router(state: ResearchState) -> str:
    if state["market_strategy_review"].decision == ReviewDecision.APPROVED:
        return "approved"
    return "revision"


def market_strategy_revision_router(state: ResearchState) -> str:
    if state.get("revision_limit_reached", False):
        return "report"
    target = state["market_strategy_review"].revision_target
    if target is None:
        raise ValueError("market strategy revision is missing a target")
    return target.value


@dataclass(frozen=True)
class MarketStrategyReportNode:
    output_path: Path
    name: str = "market_report"

    def __call__(self, state: ResearchState) -> dict:
        content = render_market_strategy_report(
            state["market_strategy_report"],
            state["analysis_bundle"],
            state["market_strategy_review"],
        )
        path = save_market_strategy_report(content, self.output_path)
        return {"report_markdown_path": str(path), "current_stage": self.name}


@dataclass(frozen=True)
class MarketStrategyHandler:
    workflow: Any
    context_provider: MarketContextProvider
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


def build_market_strategy_workflow(
    registry: AnalysisEngineRegistry,
    *,
    report_path: str | Path,
):
    graph = StateGraph(ResearchState)
    graph.add_node("market_intake", market_strategy_intake_node)
    graph.add_node("market_analysis", AnalysisExecutionNode(registry))
    graph.add_node("market_synthesis", MarketStrategySynthesisNode())
    graph.add_node("market_review", MarketStrategyReviewNode())
    graph.add_node("revision_control", revision_control_node)
    graph.add_node("market_report", MarketStrategyReportNode(Path(report_path)))

    graph.add_edge(START, "market_intake")
    graph.add_edge("market_intake", "market_analysis")
    graph.add_edge("market_analysis", "market_synthesis")
    graph.add_edge("market_synthesis", "market_review")
    graph.add_conditional_edges(
        "market_review",
        market_strategy_review_router,
        {"approved": "market_report", "revision": "revision_control"},
    )
    graph.add_conditional_edges(
        "revision_control",
        market_strategy_revision_router,
        {
            "market_analysis": "market_analysis",
            "market_synthesis": "market_synthesis",
            "report": "market_report",
        },
    )
    graph.add_edge("market_report", END)
    return graph.compile()
