# Development Workflow

Python implementation of the Software Factory workflow, using the existing `software-factory` product/UI as the reference experience.

## Iteration 1 scope

This iteration intentionally stops after validation:

```text
OPEN REPOSITORY
      ↓
CREATE JOB / REQUIREMENT
      ↓
INTAKE
      ↓
REQUIREMENTS
      ↓
TECH_SPEC
      ↓
TASKS
      ↓
REPOSITORY_PREPARATION
      ↓
REPOSITORY_ANALYSIS
      ↓
IMPLEMENT  ←─────────────┐
      ↓                  │
VALIDATE ── failed ──────┘
      ↓ passed
COMPLETED
```

Review agent, human approval and PR/MR creation are deliberately deferred to iteration 2.

## Architecture

```text
Next.js Software Factory UI
           ↓ REST / polling
FastAPI Python backend
           ↓
PostgreSQL job queue + audit events
           ↓
lease-owned worker subprocess
           ↓
LangGraph + PostgreSQL checkpoint
           ↓
per-job git worktree
           ↓
repository-aware coding provider (Codex by default)
           ↓
dynamic repository build/test validation
```

The frontend retains the Software Factory repository-first workflow:

- `/open` — register/open a repository workspace
- `/board?project=<id>` — project board and requirement creation
- `/board/<job-id>?project=<id>` — live job details, events, diff, changed files and validation results

The board lanes currently end at **Validation**. Iteration 2 will extend the same UI with Review, Human Approval and PR/MR lanes.

## Backend capabilities

- FastAPI API
- PostgreSQL persistent jobs, projects, events and worker leases
- LangGraph PostgreSQL checkpointing with `thread_id = job_id`
- async dispatcher + isolated worker processes
- heartbeat/lease based crash recovery
- retry failed jobs from the latest durable checkpoint
- repository cache + per-job git worktrees
- repository analysis for Maven/Gradle/Node/Python/Go/Rust/.NET
- repository instruction discovery (`AGENTS.md`, `CLAUDE.md`, `README.md`, `CONTRIBUTING.md`)
- Codex CLI provider with structured result contract
- provider-independent custom command adapter
- dynamic install/test/build validation
- validation feedback loop back into implementation
- workflow event history and stage timing metrics

## Local development

### 1. PostgreSQL

```bash
docker compose up -d postgres
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

API docs: `http://localhost:8000/docs`

The default coding provider is Codex. The worker machine must have an authenticated Codex CLI installation available on `PATH`.

Check provider readiness:

```bash
curl http://localhost:8000/api/coding-provider/status
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

Default frontend configuration:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

## Using the UI

1. Open `/open` and register a repository URL/path plus base branch.
2. Enter the repository board.
3. Create a job with a title and requirement description.
4. The Python worker prepares the worktree and analyzes the repository.
5. Codex implements the requirement in the isolated worktree.
6. Repository-specific tests/build commands run automatically.
7. Failed validation is supplied back to the implementation agent, up to the configured attempt limit.
8. Open the job card to inspect the event history, changed files, git diff, stage timings and validation status.
9. Failed workflow jobs can be re-queued from the UI and resume from their persisted LangGraph checkpoint.

## Key configuration

```env
MAX_WORKERS=2
WORKER_POLL_INTERVAL_SECONDS=1.0
WORKER_HEARTBEAT_INTERVAL_SECONDS=5.0
WORKER_LEASE_SECONDS=30
WORKSPACE_COMMAND_TIMEOUT_SECONDS=900
CODING_PROVIDER=codex
CODEX_BINARY=codex
CODEX_MODEL=
CODING_AGENT_TIMEOUT_SECONDS=1800
MAX_IMPLEMENTATION_ATTEMPTS=3
RUN_INSTALL_BEFORE_VALIDATION=true
```

## Iteration 2

The next iteration will extend the current graph and the reused Software Factory frontend with:

```text
VALIDATE
   ↓
REVIEW
   ├── changes requested → IMPLEMENT
   ↓
HUMAN APPROVAL
   ├── changes requested → IMPLEMENT
   ↓
COMMIT / PUSH
   ↓
PR / MR
```

CI/CD feedback and same-MR remediation can then be layered on top of that delivery flow.
