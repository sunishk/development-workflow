# Development Workflow

AI-assisted software development workflow built with Python, FastAPI, LangGraph, and PostgreSQL.

## Architecture

```text
Client
  ↓
FastAPI
  ↓
persist QUEUED job + audit events
  ↓
DB-backed dispatcher
  ↓
lease-owned isolated Python worker
  ↓
heartbeat → PostgreSQL
  ↓
LangGraph
  ├── PostgreSQL checkpoint
  ├── factory_jobs status/lease
  └── workflow_events audit history
```

- **FastAPI** — accepts jobs and returns `202 Accepted` without waiting for workflow completion
- **Worker manager** — polls PostgreSQL for queued work and atomically claims jobs
- **Worker subprocess** — executes one workflow job in an isolated Python process
- **Worker lease/heartbeat** — records worker ownership and renews a bounded lease while work is active
- **LangGraph** — workflow orchestration and durable execution state
- **PostgreSQL** — persistent job data, queue state, worker leases, workflow events, test controls, and LangGraph checkpoints
- **Next.js** — frontend (to be added)
- **Jira / GitLab** — planned integrations

## Job lifecycle

```text
CREATED
   ↓
QUEUED
   ↓
DISPATCHING + lease
   ↓
RUNNING + heartbeat
   ├──→ FAILED ──retry──→ QUEUED
   ↓
COMPLETED
```

`POST /api/jobs` persists a job, records `JOB_CREATED` and `JOB_QUEUED`, and returns it in `QUEUED` state. The dispatcher claims the job using `FOR UPDATE SKIP LOCKED`, assigns a unique `worker_id`, sets a lease expiration, and starts a separate process using:

```bash
python -m app.worker <job-id> <worker-id>
```

The worker uses the job ID as the LangGraph `thread_id`. If no checkpoint exists, it starts with the initial graph state. If a checkpoint already exists, such as after a failed attempt or restart, it invokes the graph with the same thread and resumes from the persisted state.

## Worker leases and heartbeat

A claimed job stores:

```text
worker_id
heartbeat_at
lease_expires_at
```

The child worker periodically renews the lease. The dispatcher checks for `DISPATCHING` or `RUNNING` jobs whose lease has expired. A stale lease is treated as an interrupted worker: the job is returned to `QUEUED`, worker ownership is cleared, and `LEASE_EXPIRED` / `JOB_REQUEUED` audit events are recorded.

Worker ownership is checked before workflow completion is persisted. A stale worker that has lost ownership is therefore prevented from marking the job complete.

Default settings:

```text
WORKER_HEARTBEAT_INTERVAL_SECONDS=5.0
WORKER_LEASE_SECONDS=30
```

The lease should remain comfortably longer than the heartbeat interval.

## Workflow

```text
INTAKE → REQUIREMENTS → TECH_SPEC → TASKS → END
```

## Workflow event / audit history

Important lifecycle actions are stored in the `workflow_events` table. Current event types include:

```text
JOB_CREATED
JOB_QUEUED
JOB_CLAIMED
WORKER_PROCESS_STARTED
WORKFLOW_STARTED
WORKFLOW_RESUMED
WORKFLOW_COMPLETED
WORKFLOW_FAILED
RETRY_QUEUED
LEASE_EXPIRED
JOB_REQUEUED
WORKER_START_FAILED
WORKER_EXITED
```

Retrieve a job's ordered audit history with:

```bash
curl http://localhost:8000/api/jobs/<job-id>/events
```

Example response:

```json
[
  {
    "id": 1,
    "event_type": "JOB_CREATED",
    "stage": "CREATED",
    "message": null,
    "worker_id": null,
    "created_at": "2026-09-12T08:00:00Z"
  },
  {
    "id": 4,
    "event_type": "WORKFLOW_STARTED",
    "stage": "CREATED",
    "message": null,
    "worker_id": "...",
    "created_at": "2026-09-12T08:00:01Z"
  }
]
```

This event stream is intended to become the source for cycle-time, retry, failure, and AI-productivity metrics later.

## Failure and retry

When a workflow stage raises an exception:

1. The worker marks the job `FAILED`.
2. The error is persisted in PostgreSQL.
3. LangGraph retains the latest successful checkpoint.
4. `WORKFLOW_FAILED` is added to the audit history.
5. `POST /api/jobs/{job_id}/retry` changes the job back to `QUEUED`, records `RETRY_QUEUED`, and immediately returns `202 Accepted`.
6. A worker later picks up the same job ID and resumes using the existing checkpoint.

The automated test `backend/tests/test_failure_retry.py` verifies checkpoint resume behavior. `backend/tests/test_worker_isolation.py` verifies that workflow jobs are launched through a separate Python process and retain both job and worker ownership identifiers.

### Restart recovery

On startup and during dispatch polling, stale `DISPATCHING`/`RUNNING` leases are returned to `QUEUED`. On graceful shutdown, active worker processes are terminated and unfinished jobs are re-queued. Because LangGraph checkpoints are persisted, replacement workers can continue from the last durable graph state.

## Manual failure/retry demo

Development-only failure controls are persisted in PostgreSQL so isolated worker processes can see them.

Configure one failure:

```bash
curl -X POST http://localhost:8000/api/test/failure \
  -H 'Content-Type: application/json' \
  -d '{"stage":"TECH_SPEC","failures":1}'
```

Create a job:

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{"title":"Retry demo","description":"Verify checkpoint recovery"}'
```

The create response should initially contain `"status":"QUEUED"`. Poll until it becomes `FAILED`:

```bash
curl http://localhost:8000/api/jobs/<job-id>
```

Inspect the audit history:

```bash
curl http://localhost:8000/api/jobs/<job-id>/events
```

Queue the retry:

```bash
curl -X POST http://localhost:8000/api/jobs/<job-id>/retry
```

Poll again until the worker completes it:

```bash
curl http://localhost:8000/api/jobs/<job-id>
```

Clear the development failure control afterward:

```bash
curl -X DELETE http://localhost:8000/api/test/failure
```

Test controls are only registered when `ENVIRONMENT` is not `production`.

## Local development

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Start the backend from the `backend` directory. This matters because worker subprocesses use that directory as their default working directory:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Run the automated tests:

```bash
pytest -q
```

API docs are available at `http://localhost:8000/docs`.

## Worker configuration

```text
MAX_WORKERS=2
WORKER_POLL_INTERVAL_SECONDS=1.0
WORKER_CWD=.
WORKER_HEARTBEAT_INTERVAL_SECONDS=5.0
WORKER_LEASE_SECONDS=30
```

`MAX_WORKERS` limits concurrent child processes for a single API instance. PostgreSQL leases provide stale-worker recovery and ownership protection; a later production milestone should add formal Alembic migrations and stronger idempotency around external side effects before horizontally scaling workers aggressively.
