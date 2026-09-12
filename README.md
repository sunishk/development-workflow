# Development Workflow

AI-assisted software development workflow built with Python, FastAPI, LangGraph, and PostgreSQL.

## Architecture

```text
Client
  ↓
FastAPI
  ↓
persist QUEUED job
  ↓
DB-backed dispatcher
  ↓
isolated Python worker process
  ↓
LangGraph
  ├── PostgreSQL checkpoint
  └── factory_jobs status
```

- **FastAPI** — accepts jobs and returns `202 Accepted` without waiting for workflow completion
- **Worker manager** — polls PostgreSQL for queued work and atomically claims jobs
- **Worker subprocess** — executes one workflow job in an isolated Python process
- **LangGraph** — workflow orchestration and durable execution state
- **PostgreSQL** — persistent job data, queue state, test controls, and LangGraph checkpoints
- **Next.js** — frontend (to be added)
- **Jira / GitLab** — planned integrations

## Job lifecycle

```text
CREATED
   ↓
QUEUED
   ↓
DISPATCHING
   ↓
RUNNING
   ├──→ FAILED ──retry──→ QUEUED
   ↓
COMPLETED
```

`POST /api/jobs` only persists a job and returns it in `QUEUED` state. The dispatcher starts a separate process using:

```bash
python -m app.worker <job-id>
```

The worker uses the job ID as the LangGraph `thread_id`. If no checkpoint exists, it starts with the initial graph state. If a checkpoint already exists, such as after a failed attempt or restart, it invokes the graph with the same thread and resumes from the persisted state.

The dispatcher uses PostgreSQL row locking with `FOR UPDATE SKIP LOCKED` so multiple dispatcher instances can safely compete for queued jobs without intentionally claiming the same row.

## Workflow

```text
INTAKE → REQUIREMENTS → TECH_SPEC → TASKS → END
```

## Failure and retry

When a workflow stage raises an exception:

1. The worker marks the job `FAILED`.
2. The error is persisted in PostgreSQL.
3. LangGraph retains the latest successful checkpoint.
4. `POST /api/jobs/{job_id}/retry` changes the job back to `QUEUED` and immediately returns `202 Accepted`.
5. A worker later picks up the same job ID and resumes using the existing checkpoint.

The automated test `backend/tests/test_failure_retry.py` verifies checkpoint resume behavior. `backend/tests/test_worker_isolation.py` verifies that workflow jobs are launched through a separate Python process and retain the same job ID.

### Restart recovery

On API startup, jobs left in `DISPATCHING` or `RUNNING` are moved back to `QUEUED`. On graceful shutdown, active worker processes are terminated and their unfinished jobs are re-queued. Because LangGraph checkpoints are persisted, the replacement worker can continue from the last durable graph state.

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
```

`MAX_WORKERS` limits concurrent child processes for a single API instance. This is intentionally a simple first worker layer; a later production milestone can separate the dispatcher into its own service and add leases/heartbeats for stronger distributed-worker guarantees.
