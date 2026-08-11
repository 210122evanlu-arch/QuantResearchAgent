"""End-to-end statistical event-study graph with committee revision control."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.event_study import (
    EventStudyExecutionNode,
    EventStudyReviewNode,
    EventStudySynthesisNode,
)
from graph.intent_router import intent_router_node
from graph.router import revision_control_node
from schemas.enums import ReviewDecision, TaskType
from schemas.platform import EvidenceRecord, ResearchRequest
from schemas.state import ResearchState
from tools.event_study_report import render_event_study_report, save_event_study_report

EventStudyContextProvider = Callable[[ResearchRequest], Mapping[str, Any]]


def event_study_intake_node(state: dict[str, Any]) -> dict:
    request = state.get("request")
    if request is None:
        raise ValueError("event study requires a request")
    if not isinstance(request, ResearchRequest):
        request = ResearchRequest.model_validate(request)
    if request.task_type != TaskType.EVENT_STUDY:
        raise ValueError("event study workflow requires task_type=event_study")
    return intent_router_node({"request": request})


def event_study_review_router(state: ResearchState) -> str:
    if state["event_study_review"].decision == ReviewDecision.APPROVED:
        return "approved"
    return "revision"


def event_study_revision_router(state: ResearchState) -> str:
    if state.get("revision_limit_reached", False):
        return "report"
    target = state["event_study_review"].revision_target
    if target is None:
        raise ValueError("event study revision is missing a target")
    return target.value


@dataclass(frozen=True)
class EventStudyReportNode:
    output_path: Path
    name: str = "event_report"

    def __call__(self, state: ResearchState) -> dict:
        evidence = [
            item
            if isinstance(item, EvidenceRecord)
            else EvidenceRecord.model_validate(item)
            for item in state["analysis_context"].get("evidence", [])
        ]
        content = render_event_study_report(
            state["event_study_report"],
            state["event_study_result"],
            state["event_study_review"],
            evidence,
        )
        path = save_event_study_report(content, self.output_path)
        return {"report_markdown_path": str(path), "current_stage": self.name}


@dataclass(frozen=True)
class EventStudyHandler:
    workflow: Any
    context_provider: EventStudyContextProvider
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


def build_event_study_workflow(*, report_path: str | Path):
    """Compile intake, execution, synthesis, committee, revision, and report."""
    graph = StateGraph(ResearchState)
    graph.add_node("event_intake", event_study_intake_node)
    graph.add_node("event_execution", EventStudyExecutionNode())
    graph.add_node("event_synthesis", EventStudySynthesisNode())
    graph.add_node("event_review", EventStudyReviewNode())
    graph.add_node("revision_control", revision_control_node)
    graph.add_node("event_report", EventStudyReportNode(Path(report_path)))

    graph.add_edge(START, "event_intake")
    graph.add_edge("event_intake", "event_execution")
    graph.add_edge("event_execution", "event_synthesis")
    graph.add_edge("event_synthesis", "event_review")
    graph.add_conditional_edges(
        "event_review",
        event_study_review_router,
        {"approved": "event_report", "revision": "revision_control"},
    )
    graph.add_conditional_edges(
        "revision_control",
        event_study_revision_router,
        {
            "event_execution": "event_execution",
            "event_synthesis": "event_synthesis",
            "report": "event_report",
        },
    )
    graph.add_edge("event_report", END)
    return graph.compile()
