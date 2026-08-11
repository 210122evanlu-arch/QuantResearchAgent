"""LangGraph topology for the financial research workflow."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents import (
    data_preparation_node,
    experiment_node,
    model_design_node,
    report_node,
    research_analysis_node,
    research_manager_node,
    review_node,
)
from graph.router import (
    review_decision_router,
    revision_control_node,
    revision_target_router,
)
from graph.state import ResearchState

NodeFunction = Callable[[ResearchState], dict[str, Any]]


@dataclass(frozen=True)
class WorkflowNodes:
    """Injectable node implementations used by production and tests."""

    research_manager: NodeFunction = research_manager_node
    research_analysis: NodeFunction = research_analysis_node
    model_design: NodeFunction = model_design_node
    data_preparation: NodeFunction = data_preparation_node
    experiment: NodeFunction = experiment_node
    review: NodeFunction = review_node
    report: NodeFunction = report_node


def build_workflow(nodes: WorkflowNodes | None = None):
    """Build and compile the seven-stage workflow with revision routing."""
    nodes = nodes or WorkflowNodes()
    graph = StateGraph(ResearchState)

    graph.add_node("research_manager", nodes.research_manager)
    graph.add_node("research_analysis", nodes.research_analysis)
    graph.add_node("model_design", nodes.model_design)
    graph.add_node("data_preparation", nodes.data_preparation)
    graph.add_node("experiment", nodes.experiment)
    graph.add_node("review", nodes.review)
    graph.add_node("revision_router", revision_control_node)
    graph.add_node("report", nodes.report)

    graph.add_edge(START, "research_manager")
    graph.add_edge("research_manager", "research_analysis")
    graph.add_edge("research_analysis", "model_design")
    graph.add_edge("model_design", "data_preparation")
    graph.add_edge("data_preparation", "experiment")
    graph.add_edge("experiment", "review")

    graph.add_conditional_edges(
        "review",
        review_decision_router,
        {
            "approved": "report",
            "revision": "revision_router",
        },
    )
    graph.add_conditional_edges(
        "revision_router",
        revision_target_router,
        {
            "model_design": "model_design",
            "data_preparation": "data_preparation",
            "experiment": "experiment",
            "report": "report",
        },
    )

    graph.add_edge("report", END)
    return graph.compile()
