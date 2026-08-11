"""Traceable final research report produced from verified workflow artifacts."""

from pydantic import BaseModel, Field, model_validator

from schemas.common import PaperReference
from schemas.enums import Estimator, ReviewDecision
from schemas.experiment import (
    ModelMetrics,
    PortfolioCellResult,
    RobustnessCheck,
    StatisticalResult,
)
from schemas.review import ReviewIssue


class FinalReport(BaseModel):
    title: str
    executive_summary: str
    research_background: str
    hypotheses: list[str] = Field(min_length=1)
    methodology: str
    data_description: str
    findings: list[str] = Field(min_length=1)
    robustness_summary: str
    risk_disclosures: list[str] = Field(min_length=1)
    limitations: list[str]
    recommendations: list[str]
    review_decision: ReviewDecision
    conclusion: str

    model_name: str
    formula: str
    estimator: Estimator
    experiment_method: str
    data_sample_size: int = Field(ge=0)
    experiment_sample_size: int = Field(ge=0)
    data_fingerprint: str
    prepared_data_fingerprint: str | None = None
    experiment_data_fingerprint: str | None = None
    model_metrics: ModelMetrics
    statistical_findings: list[StatisticalResult] = Field(min_length=1)
    portfolio_results: list[PortfolioCellResult] = Field(default_factory=list)
    robustness_checks: list[RobustnessCheck]
    references: list[PaperReference] = Field(min_length=1)
    unresolved_issues: list[ReviewIssue] = Field(default_factory=list)
    source_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    artifact_path: str | None = None

    @model_validator(mode="after")
    def validate_report_status_and_counts(self) -> "FinalReport":
        if self.experiment_sample_size != self.model_metrics.observations:
            raise ValueError(
                "experiment_sample_size must match model_metrics.observations"
            )
        blocking = [issue for issue in self.unresolved_issues if issue.blocking]
        if self.review_decision == ReviewDecision.APPROVED and blocking:
            raise ValueError(
                "approved report cannot contain unresolved blocking issues"
            )
        if self.review_decision == ReviewDecision.NEED_REVISION and not any(
            "approval was not obtained" in disclosure.casefold()
            for disclosure in self.risk_disclosures
        ):
            raise ValueError(
                "unapproved report must disclose that committee approval was not obtained"
            )
        return self
