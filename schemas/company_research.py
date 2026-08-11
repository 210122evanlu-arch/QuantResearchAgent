"""Contracts for evidence-grounded listed-company research."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from schemas.enums import IssueSeverity, ReviewDecision


class CompanyResearchRevisionTarget(StrEnum):
    ANALYSIS = "company_analysis"
    SYNTHESIS = "company_synthesis"


class CompanyResearchReport(BaseModel):
    title: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    security_code: str = Field(min_length=1)
    as_of_date: date
    executive_summary: str = Field(min_length=1)
    business_model: str = Field(min_length=1)
    competitive_position: str = Field(min_length=1)
    financial_quality: str = Field(min_length=1)
    peer_comparison: str = Field(min_length=1)
    valuation: str = Field(min_length=1)
    catalysts: list[str] = Field(min_length=1)
    risks: list[str] = Field(min_length=1)
    monitoring_indicators: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    conclusion: str = Field(min_length=1)


class CompanyResearchReviewIssue(BaseModel):
    severity: IssueSeverity
    description: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    target: CompanyResearchRevisionTarget
    blocking: bool = True


class CompanyResearchReviewResult(BaseModel):
    decision: ReviewDecision
    strengths: list[str] = Field(default_factory=list)
    issues: list[CompanyResearchReviewIssue] = Field(default_factory=list)
    revision_target: CompanyResearchRevisionTarget | None = None
    overall_assessment: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_review_route(self) -> "CompanyResearchReviewResult":
        blocking = [issue for issue in self.issues if issue.blocking]
        if self.decision == ReviewDecision.APPROVED:
            if blocking or self.revision_target is not None:
                raise ValueError("approved company research cannot require revision")
        else:
            if not blocking or self.revision_target is None:
                raise ValueError(
                    "need_revision company research requires a blocking issue and target"
                )
            if self.revision_target not in {issue.target for issue in blocking}:
                raise ValueError("revision_target must match a blocking issue target")
        return self
