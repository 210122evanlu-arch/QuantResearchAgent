"""Structured contracts for disclosure and news event intelligence."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from schemas.enums import IssueSeverity
from schemas.platform import EvidenceRecord


class EventSourceType(StrEnum):
    OFFICIAL_DISCLOSURE = "official_disclosure"
    REGULATORY_SOURCE = "regulatory_source"
    NEWS = "news"


class EventCategory(StrEnum):
    EARNINGS = "earnings"
    OPERATIONS = "operations"
    CAPITAL_ALLOCATION = "capital_allocation"
    GOVERNANCE = "governance"
    REGULATORY = "regulatory"
    TRANSACTION = "transaction"
    LITIGATION = "litigation"
    OTHER = "other"


class ImpactDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


class ResearchUpdateAction(StrEnum):
    NO_ACTION = "no_action"
    WATCHLIST = "watchlist"
    REFRESH_REPORT = "refresh_report"
    ESCALATE_REVIEW = "escalate_review"


class ResearchEvent(BaseModel):
    event_id: str = Field(min_length=1)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{16}$")
    company_name: str = Field(min_length=1)
    security_code: str = Field(pattern=r"^\d{6}\.(?:SH|SZ)$")
    title: str = Field(min_length=1)
    published_at: datetime
    source_type: EventSourceType
    category: EventCategory
    direction: ImpactDirection
    materiality: IssueSeverity
    evidence_ids: list[str] = Field(min_length=1)
    affected_sections: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class EventIntelligenceResult(BaseModel):
    company_name: str = Field(min_length=1)
    security_code: str = Field(pattern=r"^\d{6}\.(?:SH|SZ)$")
    as_of_date: date
    report_as_of_date: date
    events: list[ResearchEvent] = Field(default_factory=list)
    duplicate_count: int = Field(ge=0)
    action: ResearchUpdateAction
    trigger_event_ids: list[str] = Field(default_factory=list)
    affected_sections: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def triggers_reference_events(self) -> "EventIntelligenceResult":
        known = {event.event_id for event in self.events}
        if missing := set(self.trigger_event_ids) - known:
            raise ValueError(
                "trigger_event_ids reference unknown events: " + ", ".join(missing)
            )
        return self


class EventAnalysisRequest(BaseModel):
    company_name: str = Field(min_length=1)
    security_code: str = Field(pattern=r"^\d{6}\.(?:SH|SZ)$")
    as_of_date: date
    report_as_of_date: date
    evidence: list[EvidenceRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def report_precedes_analysis(self) -> "EventAnalysisRequest":
        if self.report_as_of_date > self.as_of_date:
            raise ValueError("report_as_of_date must not be after as_of_date")
        return self
