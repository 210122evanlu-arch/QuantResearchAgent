"""Deterministic Debate Gate and optional debate pipeline assembly."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langgraph.graph import END, START, StateGraph

from schemas.debate import DebateGateResult
from schemas.enums import (
    DebateGateDecision,
    DebateTrigger,
    EvidenceStatus,
    TaskType,
)
from schemas.platform import AnalysisBundle, ResearchRequest
from schemas.state import ResearchState


@dataclass(frozen=True)
class DebateGateConfig:
    enabled: bool = True
    max_rounds: int = 3
    confidence_threshold: float = 0.7
    material_task_types: frozenset[TaskType] = field(
        default_factory=lambda: frozenset(
            {TaskType.CORPORATE_ADVISORY, TaskType.MARKET_STRATEGY}
        )
    )

    def __post_init__(self) -> None:
        if not 1 <= self.max_rounds <= 5:
            raise ValueError("max_rounds must be between 1 and 5")
        if not 0 <= self.confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")


def evaluate_debate_gate(
    request: ResearchRequest,
    analysis: AnalysisBundle,
    config: DebateGateConfig | None = None,
) -> DebateGateResult:
    """Select debate from auditable signals, not unrestricted model preference."""
    policy = config or DebateGateConfig()
    if not policy.enabled or request.debate_requested is False:
        return DebateGateResult(
            decision=DebateGateDecision.SKIP_DEBATE,
            max_rounds=policy.max_rounds,
            rationale="Debate is disabled by platform or user configuration.",
        )

    triggers: list[DebateTrigger] = []
    if request.debate_requested is True:
        triggers.append(DebateTrigger.USER_REQUESTED)
    if request.task_type in policy.material_task_types:
        triggers.append(DebateTrigger.MATERIAL_ADVISORY)
    findings = [
        finding for artifact in analysis.artifacts for finding in artifact.findings
    ]
    if any(finding.confidence < policy.confidence_threshold for finding in findings):
        triggers.append(DebateTrigger.LOW_CONFIDENCE)
    if any(finding.status != EvidenceStatus.VERIFIED for finding in findings):
        triggers.append(DebateTrigger.UNVERIFIED_FINDING)
    if analysis.warnings:
        triggers.append(DebateTrigger.ANALYSIS_WARNING)
    if any("conflict" in warning.casefold() for warning in analysis.warnings):
        triggers.append(DebateTrigger.EVIDENCE_CONFLICT)
    triggers = list(dict.fromkeys(triggers))

    if not triggers:
        return DebateGateResult(
            decision=DebateGateDecision.SKIP_DEBATE,
            max_rounds=policy.max_rounds,
            rationale="No materiality, uncertainty, conflict, or user trigger was found.",
        )
    return DebateGateResult(
        decision=DebateGateDecision.ENTER_DEBATE,
        triggers=triggers,
        max_rounds=policy.max_rounds,
        rationale="Debate required by: " + ", ".join(item.value for item in triggers),
    )


def create_debate_gate_node(config: DebateGateConfig | None = None):
    policy = config or DebateGateConfig()

    def debate_gate_node(state: ResearchState) -> dict:
        request = state["request"]
        analysis = state["analysis_bundle"]
        result = evaluate_debate_gate(request, analysis, policy)
        return {
            "debate_gate_result": result,
            "max_debate_rounds": result.max_rounds,
            "current_stage": "debate_gate",
        }

    return debate_gate_node


def debate_gate_router(state: ResearchState) -> str:
    if state["debate_gate_result"].decision == DebateGateDecision.ENTER_DEBATE:
        return "debate"
    return "skip"


PipelineNode = Callable[[ResearchState], dict[str, Any]]


def build_gated_debate_workflow(
    analysis_node: PipelineNode,
    debate_workflow,
    *,
    gate_config: DebateGateConfig | None = None,
):
    """Build Analysis -> Gate -> optional Debate as a reusable integration test."""
    graph = StateGraph(ResearchState)
    graph.add_node("analysis", analysis_node)
    graph.add_node("debate_gate", create_debate_gate_node(gate_config))
    graph.add_node("debate", debate_workflow)
    graph.add_edge(START, "analysis")
    graph.add_edge("analysis", "debate_gate")
    graph.add_conditional_edges(
        "debate_gate",
        debate_gate_router,
        {"debate": "debate", "skip": END},
    )
    graph.add_edge("debate", END)
    return graph.compile()
