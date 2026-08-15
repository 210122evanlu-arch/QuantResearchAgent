"""Explainable financial-anomaly screening contracts for corporate advisory."""

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from schemas.enums import (
    FinancialRiskCategory,
    FinancialRiskLevel,
    IssueSeverity,
    SignOffStatus,
)


class FinancialStatementSnapshot(BaseModel):
    """Point-in-time financial inputs; monetary values must share one unit."""

    period_end: date
    publication_date: date
    revenue: float
    net_profit: float
    operating_cash_flow: float
    total_assets: float = Field(gt=0)
    accounts_receivable: float = Field(ge=0)
    inventory: float = Field(ge=0)
    current_assets: float = Field(ge=0)
    current_liabilities: float = Field(ge=0)
    interest_bearing_debt: float = Field(ge=0)
    cash_and_equivalents: float = Field(ge=0)
    gross_margin: float = Field(ge=-1, le=1)
    non_recurring_profit: float = 0.0
    evidence_ids: list[str] = Field(min_length=1)


class FinancialRiskInput(BaseModel):
    company_name: str = Field(min_length=1)
    security_code: str = Field(min_length=1)
    as_of_date: date
    current: FinancialStatementSnapshot
    prior: FinancialStatementSnapshot
    peer_gross_margin_median: float | None = Field(default=None, ge=-1, le=1)
    audit_opinion: str = "standard_unqualified"
    exchange_inquiry_count: int = Field(default=0, ge=0)
    regulatory_penalty_count: int = Field(default=0, ge=0)
    source_scope: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_point_in_time_scope(self) -> "FinancialRiskInput":
        if self.prior.period_end >= self.current.period_end:
            raise ValueError("prior period_end must be before current period_end")
        if self.current.publication_date > self.as_of_date:
            raise ValueError("current statement was not public by as_of_date")
        if self.prior.publication_date > self.as_of_date:
            raise ValueError("prior statement was not public by as_of_date")
        return self


class RiskAction(BaseModel):
    owner: str = Field(min_length=1)
    timeline: str = Field(min_length=1)
    actions: list[str] = Field(min_length=1)
    kpis: list[str] = Field(min_length=1)


class FinancialRiskSignal(BaseModel):
    signal_id: str = Field(min_length=1)
    category: FinancialRiskCategory
    label: str = Field(min_length=1)
    value: float | None = None
    threshold: str = Field(min_length=1)
    triggered: bool
    severity: IssueSeverity
    observation: str = Field(min_length=1)
    interpretation: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    action: RiskAction
    weight: float = Field(gt=0)


class FinancialRiskScorecard(BaseModel):
    company_name: str
    security_code: str
    as_of_date: date
    risk_score: float = Field(ge=0, le=100)
    risk_level: FinancialRiskLevel
    signals: list[FinancialRiskSignal] = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    methodology_version: str = Field(min_length=1)


class AuditTrail(BaseModel):
    run_id: str = Field(min_length=1)
    generated_at: datetime
    code_version: str = Field(min_length=1)
    methodology_version: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class HumanSignOff(BaseModel):
    status: SignOffStatus = SignOffStatus.PENDING
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    comments: str | None = None

    @model_validator(mode="after")
    def completed_signoff_requires_identity(self) -> "HumanSignOff":
        if self.status != SignOffStatus.PENDING and not (
            self.reviewer and self.reviewed_at
        ):
            raise ValueError("completed sign-off requires reviewer and reviewed_at")
        return self
