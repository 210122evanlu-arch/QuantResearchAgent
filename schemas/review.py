"""Research committee review output used by the graph router."""

from pydantic import BaseModel, Field, model_validator

from schemas.enums import (
    IssueSeverity,
    ProblemType,
    ReviewDecision,
    ReviewIssueOrigin,
    RevisionTarget,
)


class ReviewIssue(BaseModel):
    category: str
    problem_type: ProblemType
    severity: IssueSeverity
    description: str
    recommendation: str
    rule_id: str | None = None
    evidence: list[str] = Field(default_factory=list)
    origin: ReviewIssueOrigin = ReviewIssueOrigin.REVIEWER
    blocking: bool = True


class ReviewResult(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    issues: list[ReviewIssue] = Field(default_factory=list)
    decision: ReviewDecision
    revision_target: RevisionTarget | None = None
    overall_assessment: str

    @model_validator(mode="after")
    def validate_routing_fields(self) -> "ReviewResult":
        blocking_issues = [issue for issue in self.issues if issue.blocking]
        if self.decision == ReviewDecision.APPROVED:
            if self.revision_target is not None:
                raise ValueError("approved reviews cannot have a revision_target")
            if blocking_issues:
                raise ValueError("approved reviews cannot contain blocking issues")
        else:
            if not blocking_issues:
                raise ValueError(
                    "need_revision reviews must contain at least one blocking issue"
                )
            if self.revision_target is None:
                raise ValueError("need_revision reviews must specify revision_target")
            target_by_problem = {
                ProblemType.MODEL_ISSUE: RevisionTarget.MODEL_DESIGN,
                ProblemType.DATA_ISSUE: RevisionTarget.DATA_PREPARATION,
                ProblemType.EXPERIMENT_ISSUE: RevisionTarget.EXPERIMENT,
            }
            valid_targets = {
                target_by_problem[issue.problem_type] for issue in blocking_issues
            }
            if self.revision_target not in valid_targets:
                raise ValueError(
                    "revision_target must correspond to a blocking issue problem_type"
                )
        return self
