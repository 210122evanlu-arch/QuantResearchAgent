"""Nodes for financial-anomaly screening, draft delivery, and independent review."""

from dataclasses import dataclass
from pathlib import Path

from schemas.enums import QualityReviewDecision, SignOffStatus, TaskType
from schemas.financial_risk import HumanSignOff
from schemas.state import ResearchState
from tools.financial_risk import build_audit_trail, screen_financial_anomalies
from tools.financial_risk_report import (
    render_financial_risk_report,
    save_financial_risk_report,
)
from tools.quality_review import run_quality_review


@dataclass(frozen=True)
class FinancialRiskAnalysisNode:
    code_version: str = "working-tree"
    name: str = "financial_risk_analysis"

    def __call__(self, state: ResearchState) -> dict:
        data = state["financial_risk_input"]
        scorecard = screen_financial_anomalies(data)
        existing_trail = state.get("audit_trail")
        trail = build_audit_trail(
            data,
            scorecard,
            code_version=self.code_version,
            run_id=existing_trail.run_id if existing_trail is not None else None,
        )
        return {
            "financial_risk_scorecard": scorecard,
            "audit_trail": trail,
            "current_stage": self.name,
        }


@dataclass(frozen=True)
class FinancialRiskDraftNode:
    name: str = "draft_report"

    def __call__(self, state: ResearchState) -> dict:
        content = render_financial_risk_report(
            state["financial_risk_input"],
            state["financial_risk_scorecard"],
            state["financial_risk_evidence"],
            audit_trail=state["audit_trail"],
        )
        return {"draft_report_markdown": content, "current_stage": self.name}


@dataclass(frozen=True)
class FinancialRiskQualityReviewNode:
    name: str = "internal_quality_review"

    def __call__(self, state: ResearchState) -> dict:
        result = run_quality_review(
            state["financial_risk_input"],
            state["financial_risk_scorecard"],
            state["financial_risk_evidence"],
            state["draft_report_markdown"],
            state["audit_trail"],
        )
        return {"quality_review_result": result, "current_stage": self.name}


@dataclass(frozen=True)
class FinancialRiskDeliveryNode:
    output_path: Path
    name: str = "controlled_delivery"

    def __call__(self, state: ResearchState) -> dict:
        review = state["quality_review_result"]
        signoff = state.get("human_signoff") or HumanSignOff()
        if (
            signoff.status == SignOffStatus.APPROVED
            and review.decision != QualityReviewDecision.PASSED
        ):
            raise ValueError("human sign-off cannot override a failed quality review")
        content = render_financial_risk_report(
            state["financial_risk_input"],
            state["financial_risk_scorecard"],
            state["financial_risk_evidence"],
            quality_review=review,
            signoff=signoff,
            audit_trail=state["audit_trail"],
        )
        path = save_financial_risk_report(content, self.output_path)
        return {
            "human_signoff": signoff,
            "report_markdown_path": str(path),
            "current_stage": self.name,
        }


def financial_risk_intake_node(state: ResearchState) -> dict:
    request = state["request"]
    if request.task_type != TaskType.CORPORATE_ADVISORY:
        raise ValueError("financial risk workflow requires corporate_advisory")
    if not ({"financial_anomaly", "financial_risk"} & set(request.topics)):
        raise ValueError(
            "financial risk workflow requires financial_anomaly or financial_risk topic"
        )
    data = state["financial_risk_input"]
    scoped = {*request.companies, *request.securities}
    if data.company_name not in scoped and data.security_code not in scoped:
        raise ValueError("request scope does not match financial risk input")
    return {
        "research_question": request.question,
        "current_stage": "financial_risk_intake",
    }
