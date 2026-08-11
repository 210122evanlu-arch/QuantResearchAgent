# Operations and failure diagnostics

The API exposes process-local, non-sensitive operating signals for development,
demonstrations, and single-process deployments. Research prompts, report content,
credentials, and local filesystem paths are not included in the metrics payload.

## Runtime signals

`GET /v1/operations/metrics` returns:

- total and active jobs;
- counts by lifecycle status and service line;
- terminal-job completion rate;
- average and P95 execution time;
- failures grouped into stable diagnostic categories.

Each job also records `started_at`, `completed_at`, `duration_ms`, and, for failed
jobs, `failure_category`. Application logs use `job_id` and `task_type` as
correlation fields and redact API-key-, token-, password-, and secret-shaped values.

## Failure categories

| Category | First response |
| --- | --- |
| `validation` | Check the request scope, dates, supported offline company, and required fields. |
| `configuration` | Check Provider selection, environment variables, model name, and API credentials locally. |
| `data` | Check source availability, cutoff dates, required columns, cache integrity, and licences. |
| `provider` | Check network access, timeout policy, quota, and Provider status before retrying. |
| `report_delivery` | Check that the runner wrote the expected Markdown artifact inside the configured output directory. |
| `execution` | Inspect the correlated application log and preserve the failed input for reproduction. |

## Triage sequence

1. Confirm `/health` returns `ok`.
2. Read the job status and `failure_category`; do not paste credentials into tickets.
3. Use `job_id` to locate the corresponding structured log line.
4. Reproduce with the offline test environment or deterministic fixture.
5. Run the release evaluation and automated test suite before closing the incident.

The current registry is in memory: metrics reset when the process restarts and are
not a substitute for a persistent queue, distributed tracing, authentication, or a
production monitoring backend. The schemas provide a stable boundary for adding
those components later. Protect the metrics endpoint with deployment-level
authentication before exposing the service outside a trusted environment.
