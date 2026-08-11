"""Point-in-time public-data package for listed-company research."""

from datetime import date

from pydantic import BaseModel, Field, model_validator

from schemas.platform import EvidenceRecord


class ObservedMetric(BaseModel):
    name: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    observation_date: date
    source_evidence_id: str = Field(min_length=1)


class CompanyPublicDataPackage(BaseModel):
    company_name: str = Field(min_length=1)
    security_code: str = Field(pattern=r"^\d{6}\.(?:SH|SZ)$")
    provider_code: str = Field(pattern=r"^(?:sh|sz)\.\d{6}$")
    as_of_date: date
    market_metrics: list[ObservedMetric] = Field(min_length=1)
    financial_metrics: list[ObservedMetric] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
    look_ahead_bias_checked: bool

    @model_validator(mode="after")
    def validate_point_in_time_evidence(self) -> "CompanyPublicDataPackage":
        known = {item.evidence_id for item in self.evidence}
        referenced = {
            item.source_evidence_id
            for item in [*self.market_metrics, *self.financial_metrics]
        }
        if missing := referenced - known:
            raise ValueError(
                "company metrics reference unknown evidence_ids: "
                + ", ".join(sorted(missing))
            )
        future_metrics = [
            item.name
            for item in [*self.market_metrics, *self.financial_metrics]
            if item.observation_date > self.as_of_date
        ]
        if future_metrics:
            raise ValueError(
                "company metrics are dated after as_of_date: "
                + ", ".join(future_metrics)
            )
        future_evidence = [
            item.evidence_id
            for item in self.evidence
            if item.published_at is not None
            and item.published_at.date() > self.as_of_date
        ]
        if future_evidence:
            raise ValueError(
                "company evidence was published after as_of_date: "
                + ", ".join(future_evidence)
            )
        return self
