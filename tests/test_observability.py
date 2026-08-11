from datetime import date
from pathlib import Path

from api.schemas import FailureCategory, JobStatus
from api.service import ResearchJobService, classify_failure, safe_error_message
from config import ConfigurationError
from schemas.enums import TaskType
from schemas.platform import ResearchRequest


def _request() -> ResearchRequest:
    return ResearchRequest(
        task_type=TaskType.QUANT_RESEARCH,
        question="Test a signal",
        as_of_date=date(2026, 8, 11),
    )


def test_service_records_success_metrics(tmp_path: Path) -> None:
    def runner(request: ResearchRequest, output: Path) -> dict[str, str]:
        output.write_text("# Report\n", encoding="utf-8")
        return {"deliverable": request.task_type.value}

    service = ResearchJobService(runner, tmp_path)
    request = _request()
    job = service.submit(request)
    service.run(job.job_id, request)

    completed = service.get(job.job_id)
    assert completed is not None
    assert completed.status == JobStatus.COMPLETED
    assert completed.started_at is not None
    assert completed.duration_ms is not None and completed.duration_ms >= 0
    metrics = service.metrics()
    assert metrics.total_jobs == 1
    assert metrics.active_jobs == 0
    assert metrics.completion_rate == 1
    assert metrics.status_counts[JobStatus.COMPLETED] == 1
    assert metrics.task_counts[TaskType.QUANT_RESEARCH] == 1
    assert metrics.p95_duration_ms is not None


def test_service_classifies_and_redacts_failures(tmp_path: Path) -> None:
    def runner(request: ResearchRequest, output: Path) -> dict[str, str]:
        raise ConfigurationError("api_key=super-secret-value is invalid")

    service = ResearchJobService(runner, tmp_path)
    request = _request()
    job = service.submit(request)
    service.run(job.job_id, request)

    failed = service.get(job.job_id)
    assert failed is not None
    assert failed.status == JobStatus.FAILED
    assert failed.failure_category == FailureCategory.CONFIGURATION
    assert failed.error == "api_key=[REDACTED] is invalid"
    assert "super-secret-value" not in failed.error
    metrics = service.metrics()
    assert metrics.completion_rate == 0
    assert metrics.failure_counts[FailureCategory.CONFIGURATION] == 1


def test_failure_categories_and_safe_message_boundaries() -> None:
    class ProviderTimeout(Exception):
        pass

    assert classify_failure(FileNotFoundError()) == FailureCategory.DATA
    assert classify_failure(TimeoutError()) == FailureCategory.PROVIDER
    assert classify_failure(ProviderTimeout()) == FailureCategory.PROVIDER
    assert classify_failure(ValueError()) == FailureCategory.VALIDATION
    assert (
        classify_failure(RuntimeError("runner completed without creating a report"))
        == FailureCategory.REPORT_DELIVERY
    )
    assert classify_failure(RuntimeError()) == FailureCategory.EXECUTION
    assert safe_error_message(RuntimeError("")) == "RuntimeError"
    assert len(safe_error_message(RuntimeError("x" * 600))) == 500
