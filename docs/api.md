# Research Jobs API

The FastAPI delivery layer exposes a stable boundary around research workflows. It accepts the same `ResearchRequest` used by the platform router, tracks job lifecycle state, and serves completed Markdown reports without exposing local filesystem paths.

## Start the service

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `GET` | `/v1/operations/metrics` | Read non-sensitive lifecycle, latency, and failure aggregates |
| `GET` | `/v1/capabilities` | Service lines enabled in the bundled HTTP executor |
| `POST` | `/v1/events/analyze` | Deduplicate events and decide whether research must be refreshed |
| `POST` | `/v1/jobs` | Validate and submit a standardized research request |
| `GET` | `/v1/jobs/{job_id}` | Read lifecycle status, summary, or failure reason |
| `GET` | `/v1/jobs/{job_id}/report` | Download a completed Markdown report |

## Example request

```json
{
  "task_type": "company_research",
  "question": "研究贵州茅台的财务质量与竞争优势",
  "companies": ["贵州茅台"],
  "securities": ["600519.SH"],
  "topics": ["financial_quality", "competitive_position", "valuation"],
  "as_of_date": "2026-08-08",
  "public_data_only": true
}
```

The bundled offline executor supports the BYD corporate-advisory and Moutai company-research showcases. In this endpoint, `enabled=false` means that the bundled HTTP runner does not execute that service line; it does not mean the platform lacks an intake route or report template. See [Capability maturity](capability_status.md). `create_app(runner=...)` accepts an injected runner for production workflows, licensed data, or an external queue. The HTTP contract and job lifecycle remain unchanged.

Jobs expose start/completion timestamps, execution duration, and a stable failure category. Error messages are bounded and credential-shaped values are redacted before they enter API responses or logs. See [Operations and failure diagnostics](operations.md).

The MVP store and metrics registry are process-local. A production deployment should replace them with a persistent job repository, distributed worker, and monitoring backend while retaining the API schemas.
