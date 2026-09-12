# Productivity Dashboard API

The dashboard layer derives its metrics from `factory_jobs` and the durable `workflow_events` audit stream. Raw events remain the source of truth.

## Per-job productivity

```http
GET /api/dashboard/jobs/{job_id}
```

Example response:

```json
{
  "job_id": "...",
  "title": "Retry demo",
  "status": "COMPLETED",
  "stage": "TASKS",
  "created_at": "2026-09-12T08:00:00Z",
  "completed_at": "2026-09-12T08:00:10Z",
  "cycle_time_ms": 10000.0,
  "queue_wait_ms": 2000.0,
  "execution_time_ms": 3000.0,
  "retry_overhead_ms": 1000.0,
  "retry_count": 1,
  "failed_stage_count": 1,
  "stage_metrics": []
}
```

Definitions:

- `cycle_time_ms`: job creation to terminal completion/failure; for active jobs it runs through the current time.
- `queue_wait_ms`: job creation to first worker claim.
- `execution_time_ms`: sum of all recorded stage attempt durations.
- `retry_overhead_ms`: sum of failed stage-attempt durations.
- `retry_count`: number of `RETRY_QUEUED` events.
- `failed_stage_count`: number of stage-level `*_FAILED` events.

## Dashboard summary

```http
GET /api/dashboard/summary
```

The summary returns:

```text
total_jobs
completed_jobs
failed_jobs
active_jobs
success_rate_percent
average_cycle_time_ms
average_queue_wait_ms
total_execution_time_ms
total_retry_overhead_ms
total_retries
total_failed_stages
jobs[]
```

`success_rate_percent` uses only terminal jobs in its denominator, so queued/running jobs do not reduce the success rate.

The `jobs` array contains the same per-job productivity model returned by `/api/dashboard/jobs/{job_id}` and is intended to support an initial dashboard without requiring additional round trips.

## Dashboard use cases

This layer is ready to drive cards and charts such as:

- completed / failed / active jobs
- success rate
- average cycle time
- average queue wait
- total execution time
- retry overhead
- retries per job
- failed stages per job
- stage-level duration breakdown

A later milestone can add date/team/repository filters and AI-vs-manual baseline fields without changing the raw event model.
