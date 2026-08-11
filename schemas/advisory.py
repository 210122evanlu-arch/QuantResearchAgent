"""Company risk-advisory outputs built from public evidence."""

from datetime import date

from pydantic import BaseModel, Field

from schemas.enums import IssueSeverity


class RiskAssessment(BaseModel):
    risk_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: IssueSeverity
    impact: IssueSeverity
    likelihood: IssueSeverity
    observation: str = Field(min_length=1)
    implication: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    monitoring_indicators: list[str] = Field(min_length=1)
    mitigation_actions: list[str] = Field(min_length=1)
    action_owner: str = Field(min_length=1)
    timeline: str = Field(min_length=1)
    kpis: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class CompanyRiskProfile(BaseModel):
    company_name: str = Field(min_length=1)
    security_code: str = Field(min_length=1)
    as_of_date: date
    assessments: list[RiskAssessment] = Field(min_length=1)
    resilience_factors: list[str] = Field(default_factory=list)
    scope_limitations: list[str] = Field(min_length=1)
