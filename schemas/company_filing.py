"""Structured annual-report extraction and evidence-grounded interpretation."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from schemas.platform import EvidenceRecord


class FilingSectionTopic(StrEnum):
    BUSINESS_MODEL = "business_model"
    MANAGEMENT_DISCUSSION = "management_discussion"
    SEGMENT_INFORMATION = "segment_information"
    CASH_FLOW = "cash_flow"
    RISK_FACTORS = "risk_factors"


class FilingPageSection(BaseModel):
    evidence_id: str = Field(min_length=1)
    topic: FilingSectionTopic
    page_number: int = Field(ge=1)
    matched_keywords: list[str] = Field(min_length=1)
    text: str = Field(min_length=40, max_length=5000)


class FilingExtractionResult(BaseModel):
    source_evidence_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_url: str
    local_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(ge=1)
    extracted_characters: int = Field(ge=1)
    sections: list[FilingPageSection] = Field(min_length=1)
    page_evidence: list[EvidenceRecord] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_page_evidence(self) -> "FilingExtractionResult":
        known = {item.evidence_id for item in self.page_evidence}
        referenced = {item.evidence_id for item in self.sections}
        if missing := referenced - known:
            raise ValueError(
                "filing sections reference unknown evidence_ids: "
                + ", ".join(sorted(missing))
            )
        if any(item.page_number > self.page_count for item in self.sections):
            raise ValueError("filing section page exceeds page_count")
        return self


class CompanyFilingFinding(BaseModel):
    category: FilingSectionTopic
    statement: str = Field(min_length=1)
    implication: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class CompanyFilingAnalysis(BaseModel):
    executive_summary: str = Field(min_length=1)
    business_model: str = Field(min_length=1)
    competitive_position: str = Field(min_length=1)
    management_priorities: list[str] = Field(min_length=1)
    findings: list[CompanyFilingFinding] = Field(min_length=3, max_length=10)
    risks: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
