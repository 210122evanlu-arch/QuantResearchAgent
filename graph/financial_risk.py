"""Corporate financial-risk workflow with quality remediation and sign-off."""

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from agents.financial_risk import (
    FinancialRiskAnalysisNode,
    FinancialRiskDeliveryNode,
    FinancialRiskDraftNode,
    FinancialRiskQualityReviewNode,
    financial_risk_intake_node,
)
from graph.router import revision_control_node
from schemas.enums import QualityReviewDecision
from schemas.state import ResearchState


def quality_decision_router(state: ResearchState) -> str:
    decision = state["quality_review_result"].decision
    if decision == QualityReviewDecision.PASSED:
        return "passed"
    if decision == QualityReviewDecision.REMEDIATION_REQUIRED:
        return "remediation"
    return "blocked"


def quality_revision_router(state: ResearchState) -> str:
    if state.get("revision_limit_reached", False):
        return "delivery"
    target = state["quality_review_result"].revision_target
    if target is None:
        raise ValueError("quality remediation is missing a revision target")
    if target.value == "evidence_collection":
        return "analysis"
    if target.value == "financial_risk_analysis":
        return "analysis"
    return "draft"


def build_financial_risk_workflow(
    *,
    report_path: str | Path,
    code_version: str = "working-tree",
):
    """Compile screen -> draft -> IQR -> remediation -> controlled delivery."""
    graph = StateGraph(ResearchState)
    graph.add_node("intake", financial_risk_intake_node)
    graph.add_node("analysis", FinancialRiskAnalysisNode(code_version=code_version))
    graph.add_node("draft", FinancialRiskDraftNode())
    graph.add_node("quality_review", FinancialRiskQualityReviewNode())
    graph.add_node("revision_control", revision_control_node)
    graph.add_node("delivery", FinancialRiskDeliveryNode(Path(report_path)))

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "analysis")
    graph.add_edge("analysis", "draft")
    graph.add_edge("draft", "quality_review")
    graph.add_conditional_edges(
        "quality_review",
        quality_decision_router,
        {
            "passed": "delivery",
            "remediation": "revision_control",
            "blocked": "delivery",
        },
    )
    graph.add_conditional_edges(
        "revision_control",
        quality_revision_router,
        {"analysis": "analysis", "draft": "draft", "delivery": "delivery"},
    )
    graph.add_edge("delivery", END)
    return graph.compile()
