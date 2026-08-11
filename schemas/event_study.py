"""Structured contracts for statistical event studies and committee review."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from schemas.enums import IssueSeverity, ReviewDecision


class ReturnModel(StrEnum):
    MARKET_MODEL = "market_model"
    MARKET_ADJUSTED = "market_adjusted"


class EventStudyRevisionTarget(StrEnum):
    EXECUTION = "event_execution"
    SYNTHESIS = "event_synthesis"


class EventStudyDesign(BaseModel):
    company_name: str = Field(min_length=1)
    security_code: str = Field(pattern=r"^\d{6}\.(?:SH|SZ)$")
    event_title: str = Field(min_length=1)
    event_date: date
    benchmark_name: str = Field(min_length=1)
    return_model: ReturnModel = ReturnModel.MARKET_MODEL
    estimation_window: tuple[int, int] = (-120, -21)
    event_windows: list[tuple[int, int]] = Field(
        default_factory=lambda: [(-1, 1), (-2, 2)], min_length=1
    )
    significance_level: float = Field(default=0.05, gt=0, lt=1)

    @model_validator(mode="after")
    def validate_windows(self) -> "EventStudyDesign":
        start, end = self.estimation_window
        if start > end or end >= 0:
            raise ValueError("estimation_window must be ordered and pre-event")
        if any(
            start > end or start > 0 or end < 0 for start, end in self.event_windows
        ):
            raise ValueError("event windows must be ordered and contain day zero")
        return self


class DailyAbnormalReturn(BaseModel):
    relative_day: int
    trading_date: date
    security_return: float
    benchmark_return: float
    expected_return: float
    abnormal_return: float


class EventWindowResult(BaseModel):
    start_day: int
    end_day: int
    observations: int = Field(ge=1)
    cumulative_abnormal_return: float
    average_abnormal_return: float
    standard_error: float = Field(ge=0)
    t_stat: float | None = None
    p_value: float | None = Field(default=None, ge=0, le=1)
    significant: bool


class EventStudyResult(BaseModel):
    design: EventStudyDesign
    estimation_observations: int = Field(ge=1)
    alpha: float
    beta: float
    residual_std: float = Field(ge=0)
    window_results: list[EventWindowResult] = Field(min_length=1)
    daily_abnormal_returns: list[DailyAbnormalReturn] = Field(min_length=1)
    contaminated: bool = False
    warnings: list[str] = Field(default_factory=list)
    conclusion: str = Field(min_length=1)


class EventStudyReviewIssue(BaseModel):
    severity: IssueSeverity
    description: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    target: EventStudyRevisionTarget
    blocking: bool = True


class EventStudyReviewResult(BaseModel):
    decision: ReviewDecision
    strengths: list[str] = Field(default_factory=list)
    issues: list[EventStudyReviewIssue] = Field(default_factory=list)
    revision_target: EventStudyRevisionTarget | None = None
    overall_assessment: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_review_route(self) -> "EventStudyReviewResult":
        blocking = [issue for issue in self.issues if issue.blocking]
        if self.decision == ReviewDecision.APPROVED:
            if blocking or self.revision_target is not None:
                raise ValueError("approved event study cannot require revision")
        else:
            if not blocking or self.revision_target is None:
                raise ValueError(
                    "need_revision event study requires a blocking issue and target"
                )
            if self.revision_target not in {issue.target for issue in blocking}:
                raise ValueError("revision_target must match a blocking issue target")
        return self


class EventStudyReport(BaseModel):
    title: str = Field(min_length=1)
    as_of_date: date
    executive_summary: str = Field(min_length=1)
    event_background: str = Field(min_length=1)
    methodology: str = Field(min_length=1)
    findings: list[str] = Field(min_length=1)
    robustness_summary: str = Field(min_length=1)
    risks: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    conclusion: str = Field(min_length=1)
