"""Contracts for evidence-grounded industry research and committee review."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from schemas.enums import IssueSeverity, ReviewDecision


class IndustryResearchRevisionTarget(StrEnum):
    ANALYSIS = "industry_analysis"
    SYNTHESIS = "industry_synthesis"


class IndustryScenario(BaseModel):
    name: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    implications: list[str] = Field(min_length=1)
    monitoring_indicators: list[str] = Field(min_length=1)


class IndustryResearchReport(BaseModel):
    title: str = Field(min_length=1)
    industry_name: str = Field(min_length=1)
    as_of_date: date
    executive_summary: str = Field(min_length=1)
    value_chain: list[str] = Field(min_length=1)
    industry_structure: str = Field(min_length=1)
    demand_outlook: str = Field(min_length=1)
    supply_and_competition: str = Field(min_length=1)
    peer_comparison: str = Field(min_length=1)
    scenarios: list[IndustryScenario] = Field(min_length=2)
    key_metrics: dict[str, str] = Field(default_factory=dict)
    opportunities: list[str] = Field(min_length=1)
    risks: list[str] = Field(min_length=1)
    monitoring_indicators: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    conclusion: str = Field(min_length=1)


class IndustryResearchReviewIssue(BaseModel):
    severity: IssueSeverity
    description: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    target: IndustryResearchRevisionTarget
    blocking: bool = True


class IndustryResearchReviewResult(BaseModel):
    decision: ReviewDecision
    strengths: list[str] = Field(default_factory=list)
    issues: list[IndustryResearchReviewIssue] = Field(default_factory=list)
    revision_target: IndustryResearchRevisionTarget | None = None
    overall_assessment: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_review_route(self) -> "IndustryResearchReviewResult":
        blocking = [issue for issue in self.issues if issue.blocking]
        if self.decision == ReviewDecision.APPROVED:
            if blocking or self.revision_target is not None:
                raise ValueError("approved industry research cannot require revision")
        else:
            if not blocking or self.revision_target is None:
                raise ValueError(
                    "need_revision industry research requires a blocking issue and target"
                )
            if self.revision_target not in {issue.target for issue in blocking}:
                raise ValueError("revision_target must match a blocking issue target")
        return self
