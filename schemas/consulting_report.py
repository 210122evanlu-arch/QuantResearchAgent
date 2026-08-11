"""Structured narrative for a full-length management consulting report."""

from pydantic import BaseModel, Field

from schemas.enums import IssueSeverity


class ExecutiveFinding(BaseModel):
    title: str = Field(min_length=1)
    judgment: str = Field(min_length=1)
    implication: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class ConsultingRiskChapter(BaseModel):
    risk_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    severity: IssueSeverity
    diagnosis: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    leading_indicators: list[str] = Field(min_length=2)
    management_questions: list[str] = Field(min_length=2)
    recommended_actions: list[str] = Field(min_length=2)
    residual_uncertainty: str = Field(min_length=1)


class ConsultingScenario(BaseModel):
    name: str = Field(min_length=1)
    narrative: str = Field(min_length=1)
    observable_triggers: list[str] = Field(min_length=2)
    business_implications: list[str] = Field(min_length=2)
    management_response: list[str] = Field(min_length=2)


class PriorityAction(BaseModel):
    horizon: str = Field(min_length=1)
    action: str = Field(min_length=1)
    proposed_owner: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    deliverable: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class ConsultingReportNarrative(BaseModel):
    title: str = Field(min_length=1)
    subtitle: str = Field(min_length=1)
    executive_summary: str = Field(min_length=1)
    mandate_and_scope: str = Field(min_length=1)
    headline_findings: list[ExecutiveFinding] = Field(min_length=4, max_length=6)
    financial_and_operating_context: str = Field(min_length=1)
    market_context: str = Field(min_length=1)
    risk_chapters: list[ConsultingRiskChapter] = Field(min_length=5, max_length=7)
    scenarios: list[ConsultingScenario] = Field(min_length=3, max_length=3)
    priority_actions: list[PriorityAction] = Field(min_length=6, max_length=10)
    debate_synthesis: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
