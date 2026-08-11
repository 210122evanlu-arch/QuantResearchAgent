"""Thread-safe in-memory lifecycle management for research jobs."""

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from threading import Lock
from time import perf_counter
from uuid import uuid4

from api.schemas import (
    FailureCategory,
    JobStatus,
    OperationsMetrics,
    ResearchJob,
)
from config import ConfigurationError
from logging_config import redact_secrets
from schemas.enums import TaskType
from schemas.platform import ResearchRequest

JobRunner = Callable[[ResearchRequest, Path], Mapping[str, str]]
logger = logging.getLogger(__name__)


def classify_failure(exc: Exception) -> FailureCategory:
    """Map runtime exceptions to stable operational categories."""
    message = str(exc).casefold()
    exception_name = type(exc).__name__.casefold()
    if isinstance(exc, ConfigurationError):
        return FailureCategory.CONFIGURATION
    if isinstance(exc, FileNotFoundError):
        return FailureCategory.DATA
    if (
        isinstance(exc, (ConnectionError, TimeoutError))
        or "connection" in exception_name
        or "timeout" in exception_name
    ):
        return FailureCategory.PROVIDER
    if "report" in message and "without creating" in message:
        return FailureCategory.REPORT_DELIVERY
    if isinstance(exc, ValueError):
        return FailureCategory.VALIDATION
    return FailureCategory.EXECUTION


def safe_error_message(exc: Exception, limit: int = 500) -> str:
    """Return a client-safe diagnostic without credentials or unbounded payloads."""
    message = redact_secrets(str(exc)).replace("\r", " ").replace("\n", " ")
    return (message or type(exc).__name__)[:limit]


class ResearchJobService:
    def __init__(self, runner: JobRunner, report_directory: str | Path) -> None:
        self.runner = runner
        self.report_directory = Path(report_directory).resolve()
        self.report_directory.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, ResearchJob] = {}
        self._report_paths: dict[str, Path] = {}
        self._lock = Lock()

    def submit(self, request: ResearchRequest) -> ResearchJob:
        job_id = uuid4().hex
        job = ResearchJob(
            job_id=job_id,
            status=JobStatus.QUEUED,
            task_type=request.task_type,
            submitted_at=datetime.now(UTC),
        )
        with self._lock:
            self._jobs[job_id] = job
        return job.model_copy(deep=True)

    def run(self, job_id: str, request: ResearchRequest) -> None:
        output = self.report_directory / f"{job_id}.md"
        started = datetime.now(UTC)
        timer = perf_counter()
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.RUNNING
            job.started_at = started
        logger.info(
            "research_job_started job_id=%s task_type=%s",
            job_id,
            request.task_type.value,
        )
        try:
            summary = dict(self.runner(request, output))
            if not output.is_file():
                raise RuntimeError(
                    "research runner completed without creating a report"
                )
        except Exception as exc:
            duration_ms = max((perf_counter() - timer) * 1000, 0.0)
            category = classify_failure(exc)
            safe_error = safe_error_message(exc)
            with self._lock:
                job = self._jobs[job_id]
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(UTC)
                job.duration_ms = duration_ms
                job.error = safe_error
                job.failure_category = category
            logger.warning(
                "research_job_failed job_id=%s task_type=%s category=%s "
                "duration_ms=%.3f error=%s",
                job_id,
                request.task_type.value,
                category.value,
                duration_ms,
                safe_error,
            )
            return
        duration_ms = max((perf_counter() - timer) * 1000, 0.0)
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
            job.duration_ms = duration_ms
            job.report_url = f"/v1/jobs/{job_id}/report"
            job.summary = summary
            self._report_paths[job_id] = output
        logger.info(
            "research_job_completed job_id=%s task_type=%s duration_ms=%.3f",
            job_id,
            request.task_type.value,
            duration_ms,
        )

    def get(self, job_id: str) -> ResearchJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def report_path(self, job_id: str) -> Path | None:
        with self._lock:
            return self._report_paths.get(job_id)

    def metrics(self) -> OperationsMetrics:
        """Return a point-in-time aggregate without job prompts or report content."""
        with self._lock:
            jobs = [job.model_copy(deep=True) for job in self._jobs.values()]
        status_counts = {status: 0 for status in JobStatus}
        task_counts = {task_type: 0 for task_type in TaskType}
        failure_counts = {category: 0 for category in FailureCategory}
        durations: list[float] = []
        for job in jobs:
            status_counts[job.status] += 1
            task_counts[job.task_type] += 1
            if job.failure_category is not None:
                failure_counts[job.failure_category] += 1
            if job.duration_ms is not None:
                durations.append(job.duration_ms)
        completed = status_counts[JobStatus.COMPLETED]
        terminal = completed + status_counts[JobStatus.FAILED]
        ordered = sorted(durations)
        p95_index = ceil(0.95 * len(ordered)) - 1 if ordered else 0
        return OperationsMetrics(
            generated_at=datetime.now(UTC),
            total_jobs=len(jobs),
            active_jobs=(
                status_counts[JobStatus.QUEUED] + status_counts[JobStatus.RUNNING]
            ),
            completion_rate=completed / terminal if terminal else 0.0,
            average_duration_ms=(
                sum(durations) / len(durations) if durations else None
            ),
            p95_duration_ms=ordered[p95_index] if ordered else None,
            status_counts=status_counts,
            task_counts=task_counts,
            failure_counts=failure_counts,
        )
