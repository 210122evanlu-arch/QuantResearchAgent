"""Thread-safe in-memory lifecycle management for research jobs."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from api.schemas import JobStatus, ResearchJob
from schemas.platform import ResearchRequest

JobRunner = Callable[[ResearchRequest, Path], Mapping[str, str]]


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
        with self._lock:
            self._jobs[job_id].status = JobStatus.RUNNING
        try:
            summary = dict(self.runner(request, output))
            if not output.is_file():
                raise RuntimeError(
                    "research runner completed without creating a report"
                )
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(UTC)
                job.error = str(exc)
            return
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
            job.report_url = f"/v1/jobs/{job_id}/report"
            job.summary = summary
            self._report_paths[job_id] = output

    def get(self, job_id: str) -> ResearchJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def report_path(self, job_id: str) -> Path | None:
        with self._lock:
            return self._report_paths.get(job_id)
