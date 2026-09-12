# Development Workflow

AI-assisted software development workflow built with Python, FastAPI, and LangGraph.

## Architecture

```text
FastAPI
   ↓
Factory Workflow Service
   ↓
LangGraph
   ├── PostgreSQL checkpointer
   └── factory_jobs table
```

- **FastAPI** — backend API
- **LangGraph** — workflow orchestration and durable execution state
- **PostgreSQL** — persistent job data and LangGraph checkpoints
- **Next.js** — frontend (to be added)
- **Jira / GitLab** — planned integrations

## Workflow

```text
INTAKE → REQUIREMENTS → TECH_SPEC → TASKS → END
```

Every graph invocation uses the job ID as the LangGraph `thread_id`. This means the workflow state is associated with the job and survives an application restart.

## Failure and retry

When a workflow stage raises an exception:

1. The application marks the job `FAILED`.
2. The error is persisted in PostgreSQL.
3. LangGraph retains the latest successful checkpoint.
4. `POST /api/jobs/{job_id}/retry` resumes using the same `thread_id`.
5. The workflow continues from the persisted graph state rather than creating a new job.

## Local development

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Start the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

API docs are available at `http://localhost:8000/docs`.

### Create a job

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{"title":"Add payment validation","description":"Validate external payment requests"}'
```

### Check a job

```bash
curl http://localhost:8000/api/jobs/<job-id>
```

### Retry a failed job

```bash
curl -X POST http://localhost:8000/api/jobs/<job-id>/retry
```
