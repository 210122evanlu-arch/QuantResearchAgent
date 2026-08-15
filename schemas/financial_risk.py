"""Explainable financial-anomaly screening contracts for corporate advisory."""

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from schemas.enums import (
    AuditOpinionStatus,
    FinancialRiskCategory,
    FinancialRiskLevel,
    IndustryProfile,
    IssueSeverity,
    SignOffStatus,
)
from schemas.platform import EvidenceRecord


class FinancialStatementSnapshot(BaseModel):
    """Point-in-time financial inputs; monetary values must share one unit."""

    period_end: date
    publication_date: date
    revenue: float | None = None
    net_profit: float | None = None
    operating_cash_flow: float | None = None
    total_assets: float | None = Field(default=None, gt=0)
    accounts_receivable: float | None = Field(default=None, ge=0)
    inventory: float | None = Field(default=None, ge=0)
    current_assets: float | None = Field(default=None, ge=0)
    current_liabilities: float | None = Field(default=None, ge=0)
    interest_bearing_debt: float | None = Field(default=None, ge=0)
    cash_and_equivalents: float | None = Field(default=None, ge=0)
    gross_margin: float | None = Field(default=None, ge=-1, le=1)
    non_recurring_profit: float | None = None
    cash_conversion_ratio: float | None = None
    revenue_growth: float | None = None
    accounts_receivable_growth: float | None = None
    inventory_growth: float | None = None
    current_ratio: float | None = Field(default=None, ge=0)
    net_debt_to_operating_cash_flow: float | None = None
    return_on_equity: float | None = None
    return_on_assets: float | None = None
    net_profit_margin: float | None = None
    debt_to_assets: float | None = Field(default=None, ge=0)
    interest_coverage: float | None = None
    receivables_days: float | None = Field(default=None, ge=0)
    inventory_days: float | None = Field(default=None, ge=0)
    asset_turnover: float | None = Field(default=None, ge=0)
    impairment_to_assets: float | None = Field(default=None, ge=0)
    goodwill_to_assets: float | None = Field(default=None, ge=0)
    related_party_transaction_ratio: float | None = Field(default=None, ge=0)
    top_five_customer_concentration: float | None = Field(default=None, ge=0, le=1)
    top_five_supplier_concentration: float | None = Field(default=None, ge=0, le=1)
    rd_capitalization_ratio: float | None = Field(default=None, ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1)


class FinancialRiskInput(BaseModel):
    company_name: str = Field(min_length=1)
    security_code: str = Field(min_length=1)
    as_of_date: date
    current: FinancialStatementSnapshot
    prior: FinancialStatementSnapshot
    peer_gross_margin_median: float | None = Field(default=None, ge=-1, le=1)
    industry_profile: IndustryProfile = IndustryProfile.GENERAL
    audit_opinion: AuditOpinionStatus = AuditOpinionStatus.UNKNOWN
    audit_opinion_evidence_ids: list[str] = Field(default_factory=list)
    exchange_inquiry_count: int = Field(default=0, ge=0)
    exchange_inquiry_evidence_ids: list[str] = Field(default_factory=list)
    regulatory_penalty_count: int = Field(default=0, ge=0)
    regulatory_penalty_evidence_ids: list[str] = Field(default_factory=list)
    source_scope: str = Field(min_length=1)
    data_warnings: list[str] = Field(default_factory=list)

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
    available: bool = True
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
    data_coverage: float = Field(ge=0, le=1)
    signals: list[FinancialRiskSignal] = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    methodology_version: str = Field(min_length=1)
    threshold_profile: str = Field(min_length=1)


class RegulatoryDisclosureSummary(BaseModel):
    audit_opinion: AuditOpinionStatus
    exchange_inquiry_count: int = Field(ge=0)
    regulatory_penalty_count: int = Field(ge=0)
    audit_opinion_evidence_ids: list[str] = Field(default_factory=list)
    exchange_inquiry_evidence_ids: list[str] = Field(default_factory=list)
    regulatory_penalty_evidence_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FinancialRiskDataPackage(BaseModel):
    financial_input: FinancialRiskInput
    evidence: list[EvidenceRecord] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence_lineage_and_cutoff(self) -> "FinancialRiskDataPackage":
        known = {item.evidence_id for item in self.evidence}
        referenced = {
            *self.financial_input.current.evidence_ids,
            *self.financial_input.prior.evidence_ids,
            *self.financial_input.audit_opinion_evidence_ids,
            *self.financial_input.exchange_inquiry_evidence_ids,
            *self.financial_input.regulatory_penalty_evidence_ids,
        }
        if missing := referenced - known:
            raise ValueError(
                "financial risk input references unknown evidence_ids: "
                + ", ".join(sorted(missing))
            )
        if any(
            item.published_at is not None
            and item.published_at.date() > self.financial_input.as_of_date
            for item in self.evidence
        ):
            raise ValueError("financial risk evidence was published after as_of_date")
        return self


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
