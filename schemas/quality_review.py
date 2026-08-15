"""Independent engagement-quality review contracts."""

from pydantic import BaseModel, Field, model_validator

from schemas.enums import (
    IssueSeverity,
    QualityReviewCategory,
    QualityReviewDecision,
    QualityReviewTarget,
)


class QualityCheck(BaseModel):
    check_id: str = Field(min_length=1)
    category: QualityReviewCategory
    description: str = Field(min_length=1)
    passed: bool
    blocking: bool = False
    details: str = Field(min_length=1)


class QualityFinding(BaseModel):
    finding_id: str = Field(min_length=1)
    category: QualityReviewCategory
    severity: IssueSeverity
    description: str = Field(min_length=1)
    remediation: str = Field(min_length=1)
    target: QualityReviewTarget
    blocking: bool = False


class QualityReviewResult(BaseModel):
    decision: QualityReviewDecision
    checks: list[QualityCheck] = Field(min_length=1)
    findings: list[QualityFinding] = Field(default_factory=list)
    revision_target: QualityReviewTarget | None = None
    evidence_coverage: float = Field(ge=0, le=1)
    reproducible: bool
    report_consistent: bool
    human_signoff_required: bool = True
    overall_assessment: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_decision_and_target(self) -> "QualityReviewResult":
        failed = [check for check in self.checks if not check.passed]
        if self.decision == QualityReviewDecision.PASSED:
            if failed or self.findings or self.revision_target is not None:
                raise ValueError("passed quality review cannot contain failed checks")
        elif not failed or not self.findings:
            raise ValueError(
                "non-passed quality review requires failed checks and findings"
            )
        if self.decision == QualityReviewDecision.REMEDIATION_REQUIRED:
            if self.revision_target is None:
                raise ValueError("remediation requires a revision_target")
        elif self.revision_target is not None:
            raise ValueError("only remediation decisions may specify revision_target")
        return self
