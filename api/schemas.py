"""API-facing job contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from schemas.enums import TaskType


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FailureCategory(StrEnum):
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    DATA = "data"
    PROVIDER = "provider"
    REPORT_DELIVERY = "report_delivery"
    EXECUTION = "execution"


class ResearchJob(BaseModel):
    job_id: str = Field(min_length=1)
    status: JobStatus
    task_type: TaskType
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    report_url: str | None = None
    summary: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    failure_category: FailureCategory | None = None


class Capability(BaseModel):
    task_type: TaskType
    enabled: bool
    delivery: str


class HealthResponse(BaseModel):
    status: str
    service: str


class OperationsMetrics(BaseModel):
    """Non-sensitive process metrics derived from the in-memory job registry."""

    generated_at: datetime
    total_jobs: int = Field(ge=0)
    active_jobs: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=1)
    average_duration_ms: float | None = Field(default=None, ge=0)
    p95_duration_ms: float | None = Field(default=None, ge=0)
    status_counts: dict[JobStatus, int]
    task_counts: dict[TaskType, int]
    failure_counts: dict[FailureCategory, int]
