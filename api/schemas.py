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


class ResearchJob(BaseModel):
    job_id: str = Field(min_length=1)
    status: JobStatus
    task_type: TaskType
    submitted_at: datetime
    completed_at: datetime | None = None
    report_url: str | None = None
    summary: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class Capability(BaseModel):
    task_type: TaskType
    enabled: bool
    delivery: str


class HealthResponse(BaseModel):
    status: str
    service: str
