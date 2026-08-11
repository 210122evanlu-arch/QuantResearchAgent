"""Deterministic review and revision routing."""

from schemas.enums import ReviewDecision
from schemas.state import ResearchState


def review_decision_router(state: ResearchState) -> str:
    """Choose reporting or revision based only on committee decision."""
    review_result = state["review_result"]

    if review_result.decision == ReviewDecision.APPROVED:
        return "approved"

    return "revision"


def revision_control_node(state: ResearchState) -> dict:
    """Count revisions and flag studies that reached the configured limit."""
    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 3)

    if revision_count < 0 or max_revisions < 0:
        raise ValueError("revision_count and max_revisions must be non-negative")

    if revision_count >= max_revisions:
        return {"revision_limit_reached": True}

    return {
        "revision_count": revision_count + 1,
        "revision_limit_reached": False,
    }


def revision_target_router(state: ResearchState) -> str:
    """Route to the selected revision stage or force a risk-qualified report."""
    if state.get("revision_limit_reached", False):
        return "report"

    review_result = state["review_result"]

    if review_result.revision_target is None:
        raise ValueError("need_revision review is missing revision_target")

    return review_result.revision_target.value
