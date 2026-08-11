import asyncio
from datetime import date
from pathlib import Path

import httpx

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


async def _client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


def test_health_and_capability_discovery(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with await _client(create_app(report_directory=tmp_path)) as client:
            assert (await client.get("/health")).json()["status"] == "ok"
            capabilities = (await client.get("/v1/capabilities")).json()
            enabled = {item["task_type"] for item in capabilities if item["enabled"]}
            assert enabled == {
                "company_research",
                "industry_research",
                "event_study",
                "market_strategy",
                "quant_research",
                "corporate_advisory",
            }
            metrics = (await client.get("/v1/operations/metrics")).json()
            assert metrics["total_jobs"] == 0
            assert metrics["completion_rate"] == 0

    asyncio.run(scenario())


def test_submit_status_and_download_report(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with await _client(create_app(report_directory=tmp_path)) as client:
            submitted = await client.post(
                "/v1/jobs",
                json=_request(TaskType.COMPANY_RESEARCH, "贵州茅台", "600519.SH"),
            )
            assert submitted.status_code == 202
            job_id = submitted.json()["job_id"]

            job = await client.get(f"/v1/jobs/{job_id}")
            assert job.json()["status"] == JobStatus.COMPLETED
            assert job.json()["summary"]["deliverable"] == "company_research"
            assert job.json()["duration_ms"] >= 0

            report = await client.get(f"/v1/jobs/{job_id}/report")
            assert report.status_code == 200
            assert "贵州茅台酒股份有限公司" in report.text
            assert 'align="center"' in report.text

            metrics = (await client.get("/v1/operations/metrics")).json()
            assert metrics["total_jobs"] == 1
            assert metrics["status_counts"]["completed"] == 1
            assert metrics["completion_rate"] == 1

    asyncio.run(scenario())


def test_unsupported_offline_scope_is_recorded_as_failed(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with await _client(create_app(report_directory=tmp_path)) as client:
            submitted = await client.post(
                "/v1/jobs",
                json=_request(TaskType.COMPANY_RESEARCH, "示例公司", "000000.SZ"),
            )
            job_id = submitted.json()["job_id"]
            job = (await client.get(f"/v1/jobs/{job_id}")).json()
            assert job["status"] == JobStatus.FAILED
            assert "offline showcase supports" in job["error"]
            response = await client.get(f"/v1/jobs/{job_id}/report")
            assert response.status_code == 409

    asyncio.run(scenario())


def test_submit_industry_research_and_download_report(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with await _client(create_app(report_directory=tmp_path)) as client:
            submitted = await client.post(
                "/v1/jobs",
                json={
                    "task_type": TaskType.INDUSTRY_RESEARCH.value,
                    "question": "研究高端白酒行业的经营分化与情景。",
                    "industries": ["中国高端白酒"],
                    "as_of_date": "2026-08-08",
                },
            )
            assert submitted.status_code == 202
            job_id = submitted.json()["job_id"]
            job = (await client.get(f"/v1/jobs/{job_id}")).json()
            assert job["status"] == JobStatus.COMPLETED
            assert job["summary"]["deliverable"] == "industry_research"

            report = await client.get(f"/v1/jobs/{job_id}/report")
            assert report.status_code == 200
            assert "## 情景矩阵" in report.text
            assert "仅覆盖两家公司" in report.text

    asyncio.run(scenario())


def test_submit_event_study_and_download_report(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with await _client(create_app(report_directory=tmp_path)) as client:
            submitted = await client.post(
                "/v1/jobs",
                json=_request(TaskType.EVENT_STUDY, "比亚迪", "002594.SZ"),
            )
            assert submitted.status_code == 202
            job_id = submitted.json()["job_id"]
            job = (await client.get(f"/v1/jobs/{job_id}")).json()
            assert job["status"] == JobStatus.COMPLETED
            assert job["summary"]["deliverable"] == "event_study"

            report = await client.get(f"/v1/jobs/{job_id}/report")
            assert report.status_code == 200
            assert "## 方法与估计设计" in report.text
            assert "不得被解释为" in report.text

    asyncio.run(scenario())


def test_submit_market_strategy_and_download_report(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with await _client(create_app(report_directory=tmp_path)) as client:
            submitted = await client.post(
                "/v1/jobs",
                json={
                    "task_type": TaskType.MARKET_STRATEGY.value,
                    "question": "研究A股市场环境与配置情景。",
                    "as_of_date": "2025-02-28",
                },
            )
            assert submitted.status_code == 202
            job_id = submitted.json()["job_id"]
            job = (await client.get(f"/v1/jobs/{job_id}")).json()
            assert job["status"] == JobStatus.COMPLETED
            assert job["summary"]["deliverable"] == "market_strategy"

            report = await client.get(f"/v1/jobs/{job_id}/report")
            assert report.status_code == 200
            assert "## 三情景策略矩阵" in report.text
            assert "离线信号评分不代表实时市场状态" in report.text

    asyncio.run(scenario())


def test_submit_quant_research_and_download_report(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with await _client(create_app(report_directory=tmp_path)) as client:
            submitted = await client.post(
                "/v1/jobs",
                json={
                    "task_type": TaskType.QUANT_RESEARCH.value,
                    "question": "研究动量信号是否预测未来收益。",
                    "topics": ["momentum"],
                    "as_of_date": "2026-08-08",
                },
            )
            assert submitted.status_code == 202
            job_id = submitted.json()["job_id"]
            job = (await client.get(f"/v1/jobs/{job_id}")).json()
            assert job["status"] == JobStatus.COMPLETED
            assert job["summary"]["deliverable"] == "quant_research"

            report = await client.get(f"/v1/jobs/{job_id}/report")
            assert report.status_code == 200
            assert "Non-IVOL Generalisation Demo" in report.text

    asyncio.run(scenario())


def test_unknown_job_returns_404(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with await _client(create_app(report_directory=tmp_path)) as client:
            assert (await client.get("/v1/jobs/missing")).status_code == 404
            response = await client.get("/v1/jobs/missing/report")
            assert response.status_code == 404

    asyncio.run(scenario())


def test_event_analysis_endpoint_returns_refresh_decision(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with await _client(create_app(report_directory=tmp_path)) as client:
            response = await client.post(
                "/v1/events/analyze",
                json={
                    "company_name": "示例股份",
                    "security_code": "600000.SH",
                    "as_of_date": "2026-08-10",
                    "report_as_of_date": "2026-08-01",
                    "evidence": [
                        {
                            "evidence_id": "E1",
                            "source_type": "company_announcement",
                            "title": "2026年度业绩预告：利润下降",
                            "source_name": "CNInfo",
                            "url": "https://example.test/E1",
                            "published_at": "2026-08-08T00:00:00Z",
                            "retrieved_at": "2026-08-10T00:00:00Z",
                            "summary": "利润下降。",
                        }
                    ],
                },
            )
            assert response.status_code == 200
            assert response.json()["action"] == "refresh_report"
            assert response.json()["trigger_event_ids"]

    asyncio.run(scenario())
