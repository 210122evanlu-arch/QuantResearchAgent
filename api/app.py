"""FastAPI application factory for research submission and delivery."""

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.responses import FileResponse

from api.schemas import Capability, HealthResponse, JobStatus, ResearchJob
from api.service import JobRunner, ResearchJobService
from examples.business_risk_consulting_demo import run_business_risk_consulting_demo
from examples.moutai_company_research_demo import run_moutai_company_research_demo
from schemas.enums import TaskType
from schemas.platform import ResearchRequest


def offline_showcase_runner(request: ResearchRequest, output: Path) -> dict[str, str]:
    company_scope = " ".join([*request.companies, *request.securities]).lower()
    if request.task_type == TaskType.CORPORATE_ADVISORY and (
        "比亚迪" in company_scope or "byd" in company_scope or "002594" in company_scope
    ):
        result = run_business_risk_consulting_demo(output)
        return {"company": result["company"], "deliverable": "risk_advisory"}
    if request.task_type == TaskType.COMPANY_RESEARCH and (
        "贵州茅台" in company_scope
        or "moutai" in company_scope
        or "600519" in company_scope
    ):
        result = run_moutai_company_research_demo(output)
        return {
            "company": result["company_research_report"].company_name,
            "deliverable": "company_research",
        }
    raise ValueError(
        "offline showcase supports BYD corporate_advisory and Moutai company_research"
    )


def create_app(
    runner: JobRunner | None = None,
    report_directory: str | Path = "reports/api",
) -> FastAPI:
    app = FastAPI(
        title="QuantResearchAgent API",
        version="0.2.0",
        description="Submit evidence-grounded research jobs and retrieve reports.",
    )
    service = ResearchJobService(runner or offline_showcase_runner, report_directory)
    app.state.job_service = service

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="quant-research-agent")

    @app.get("/v1/capabilities", response_model=list[Capability], tags=["research"])
    def capabilities() -> list[Capability]:
        enabled = {TaskType.COMPANY_RESEARCH, TaskType.CORPORATE_ADVISORY}
        return [
            Capability(
                task_type=task_type,
                enabled=task_type in enabled,
                delivery="markdown_report" if task_type in enabled else "planned",
            )
            for task_type in TaskType
        ]

    @app.post(
        "/v1/jobs",
        response_model=ResearchJob,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["research"],
    )
    def submit_job(
        request: ResearchRequest, background_tasks: BackgroundTasks
    ) -> ResearchJob:
        job = service.submit(request)
        background_tasks.add_task(service.run, job.job_id, request)
        return job

    @app.get("/v1/jobs/{job_id}", response_model=ResearchJob, tags=["research"])
    def get_job(job_id: str) -> ResearchJob:
        job = service.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="research job not found")
        return job

    @app.get("/v1/jobs/{job_id}/report", tags=["research"])
    def download_report(job_id: str) -> FileResponse:
        job = service.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="research job not found")
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(status_code=409, detail="research report is not ready")
        path = service.report_path(job_id)
        if path is None or not path.is_file():
            raise HTTPException(
                status_code=410, detail="research report is unavailable"
            )
        return FileResponse(path, media_type="text/markdown", filename=path.name)

    return app


app = create_app()
