"""Reusable research-debate subgraph with deterministic loop protection."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.debate import ChallengerNode, ModeratorNode, ProponentNode
from schemas.debate import DebateResult, DebateRound
from schemas.enums import ModeratorDecision
from schemas.state import ResearchState

DebateNode = Callable[[ResearchState], dict[str, Any]]


@dataclass(frozen=True)
class DebateNodes:
    proponent: DebateNode
    challenger: DebateNode
    moderator: DebateNode


def initialise_debate_node(state: ResearchState) -> dict:
    """Validate loop controls before any billable model call is made."""
    maximum = state.get("max_debate_rounds", 3)
    completed = state.get("debate_round", 0)
    rounds = state.get("debate_rounds", [])
    if maximum < 1 or maximum > 5:
        raise ValueError("max_debate_rounds must be between 1 and 5")
    if completed != len(rounds):
        raise ValueError("debate_round must match the recorded round count")
    if completed != 0:
        raise ValueError("a new debate workflow must start at round zero")
    return {
        "debate_round": 0,
        "debate_rounds": [],
        "max_debate_rounds": maximum,
        "debate_limit_reached": False,
        "current_stage": "debate_initialise",
    }


def record_debate_round_node(state: ResearchState) -> dict:
    """Append exactly one completed round and calculate the hard-stop flag."""
    completed = state.get("debate_round", 0)
    maximum = state.get("max_debate_rounds", 3)
    if completed < 0 or maximum < 1:
        raise ValueError(
            "debate_round must be non-negative and maximum must be positive"
        )
    if completed >= maximum:
        raise ValueError("cannot record a debate round after the configured maximum")

    round_number = completed + 1
    assessment = state["moderator_assessment"]
    forced_stop = (
        round_number >= maximum and assessment.decision == ModeratorDecision.CONTINUE
    )
    debate_round = DebateRound(
        round_number=round_number,
        proponent=state["proponent_case"],
        challenger=state["challenger_case"],
        moderator=assessment,
    )
    return {
        "debate_rounds": [*state.get("debate_rounds", []), debate_round],
        "debate_round": round_number,
        "debate_limit_reached": forced_stop,
        "current_stage": "debate_round_control",
    }


def debate_round_router(state: ResearchState) -> str:
    """Let the moderator stop early while code retains the final hard limit."""
    if state.get("debate_limit_reached", False):
        return "conclude"
    if state["moderator_assessment"].decision == ModeratorDecision.CONCLUDE:
        return "conclude"
    return "continue"


def finalise_debate_node(state: ResearchState) -> dict:
    """Create a compact report artifact instead of exposing raw chat transcripts."""
    rounds = state.get("debate_rounds", [])
    if not rounds:
        raise ValueError("cannot finalise a debate with no completed rounds")
    final_assessment = rounds[-1].moderator
    result = DebateResult(
        rounds=rounds,
        consensus_findings=final_assessment.consensus_findings,
        disputed_findings=final_assessment.disputed_findings,
        unresolved_issues=final_assessment.unresolved_issues,
        moderator_conclusion=final_assessment.synthesis,
        stopped_by_limit=state.get("debate_limit_reached", False),
    )
    return {"debate_result": result, "current_stage": "debate_synthesis"}


def build_debate_workflow(nodes: DebateNodes):
    """Compile the optional debate subgraph for later insertion before Review."""
    graph = StateGraph(ResearchState)
    graph.add_node("debate_initialise", initialise_debate_node)
    graph.add_node("proponent", nodes.proponent)
    graph.add_node("challenger", nodes.challenger)
    graph.add_node("moderator", nodes.moderator)
    graph.add_node("round_control", record_debate_round_node)
    graph.add_node("debate_synthesis", finalise_debate_node)

    graph.add_edge(START, "debate_initialise")
    graph.add_edge("debate_initialise", "proponent")
    graph.add_edge("proponent", "challenger")
    graph.add_edge("challenger", "moderator")
    graph.add_edge("moderator", "round_control")
    graph.add_conditional_edges(
        "round_control",
        debate_round_router,
        {
            "continue": "proponent",
            "conclude": "debate_synthesis",
        },
    )
    graph.add_edge("debate_synthesis", END)
    return graph.compile()


def create_debate_workflow(llm):
    """Convenience assembly using one structured LLM for all debate roles."""
    return build_debate_workflow(
        DebateNodes(
            proponent=ProponentNode(llm),
            challenger=ChallengerNode(llm),
            moderator=ModeratorNode(llm),
        )
    )
