from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from api.schemas import JobStatus
from schemas.enums import TaskType


def _request(task_type: TaskType, company: str, security: str) -> dict:
    return {
        "task_type": task_type.value,
        "question": f"研究{company}",
        "companies": [company],
        "securities": [security],
        "as_of_date": date(2026, 8, 8).isoformat(),
    }


def test_health_and_capability_discovery(tmp_path: Path) -> None:
    client = TestClient(create_app(report_directory=tmp_path))

    assert client.get("/health").json()["status"] == "ok"
    capabilities = client.get("/v1/capabilities").json()
    enabled = {item["task_type"] for item in capabilities if item["enabled"]}
    assert enabled == {"company_research", "corporate_advisory"}


def test_submit_status_and_download_report(tmp_path: Path) -> None:
    client = TestClient(create_app(report_directory=tmp_path))

    submitted = client.post(
        "/v1/jobs",
        json=_request(TaskType.COMPANY_RESEARCH, "贵州茅台", "600519.SH"),
    )
    assert submitted.status_code == 202
    job_id = submitted.json()["job_id"]

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.json()["status"] == JobStatus.COMPLETED
    assert job.json()["summary"]["deliverable"] == "company_research"

    report = client.get(f"/v1/jobs/{job_id}/report")
    assert report.status_code == 200
    assert "贵州茅台酒股份有限公司" in report.text
    assert 'align="center"' in report.text


def test_unsupported_offline_scope_is_recorded_as_failed(tmp_path: Path) -> None:
    client = TestClient(create_app(report_directory=tmp_path))
    submitted = client.post(
        "/v1/jobs",
        json=_request(TaskType.COMPANY_RESEARCH, "示例公司", "000000.SZ"),
    )
    job_id = submitted.json()["job_id"]

    job = client.get(f"/v1/jobs/{job_id}").json()
    assert job["status"] == JobStatus.FAILED
    assert "offline showcase supports" in job["error"]
    assert client.get(f"/v1/jobs/{job_id}/report").status_code == 409


def test_unknown_job_returns_404(tmp_path: Path) -> None:
    client = TestClient(create_app(report_directory=tmp_path))
    assert client.get("/v1/jobs/missing").status_code == 404
    assert client.get("/v1/jobs/missing/report").status_code == 404
