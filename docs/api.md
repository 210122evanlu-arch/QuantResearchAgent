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
| `GET` | `/v1/capabilities` | Enabled and planned service lines |
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

The bundled offline executor supports the BYD corporate-advisory and Moutai company-research showcases. `create_app(runner=...)` accepts an injected runner for production workflows, licensed data, or an external queue. The HTTP contract and job lifecycle remain unchanged.

The MVP store is process-local. A production deployment should replace it with a persistent job repository and distributed worker while retaining the API schemas.
