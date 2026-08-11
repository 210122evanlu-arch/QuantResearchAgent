"""Platform-level intake, evidence, and analysis contracts."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from schemas.enums import (
    AnalysisMethod,
    EvidenceStatus,
    ReportAudience,
    ReportDepth,
    TaskType,
)


class ResearchRequest(BaseModel):
    """A channel-neutral request accepted by the platform entry point."""

    task_type: TaskType
    question: str = Field(min_length=1)
    objective: str | None = None
    companies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    securities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    as_of_date: date
    start_date: date | None = None
    end_date: date | None = None
    audience: ReportAudience = ReportAudience.RESEARCH_TEAM
    report_depth: ReportDepth = ReportDepth.STANDARD
    public_data_only: bool = True
    debate_requested: bool | None = None

    @model_validator(mode="after")
    def validate_scope_and_dates(self) -> "ResearchRequest":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        if self.end_date and self.end_date > self.as_of_date:
            raise ValueError("end_date must not be after as_of_date")
        scoped_tasks = {
            TaskType.COMPANY_RESEARCH,
            TaskType.CORPORATE_ADVISORY,
        }
        if self.task_type in scoped_tasks and not (self.companies or self.securities):
            raise ValueError(
                "company research and corporate advisory require a company or security"
            )
        if self.task_type == TaskType.INDUSTRY_RESEARCH and not self.industries:
            raise ValueError("industry research requires at least one industry")
        return self


class EvidenceRecord(BaseModel):
    """Traceable support for a finding; raw copyrighted content is not stored."""

    evidence_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    url: str | None = None
    document_id: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime
    page_number: int | None = Field(default=None, ge=1)
    summary: str = Field(min_length=1)
    content_hash: str | None = None


class ResearchFinding(BaseModel):
    finding_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    implication: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    status: EvidenceStatus
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def verified_findings_require_evidence(self) -> "ResearchFinding":
        if self.status == EvidenceStatus.VERIFIED and not self.evidence_ids:
            raise ValueError("verified findings require at least one evidence_id")
        return self


class AnalysisArtifact(BaseModel):
    """Method-neutral output from any deterministic or LLM-assisted engine."""

    method: AnalysisMethod
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    findings: list[ResearchFinding] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AnalysisBundle(BaseModel):
    artifacts: list[AnalysisArtifact] = Field(min_length=1)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_references_exist(self) -> "AnalysisBundle":
        known = {record.evidence_id for record in self.evidence}
        referenced = {
            evidence_id
            for artifact in self.artifacts
            for finding in artifact.findings
            for evidence_id in finding.evidence_ids
        }
        missing = referenced - known
        if missing:
            raise ValueError(
                "findings reference unknown evidence_ids: " + ", ".join(sorted(missing))
            )
        return self


class WorkflowSelection(BaseModel):
    task_type: TaskType
    workflow_name: str
    analysis_methods: list[AnalysisMethod] = Field(min_length=1)
    report_template: str
    rationale: str
