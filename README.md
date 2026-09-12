# Development AI Agent

Development AI Agent is a local AI-assisted software development workflow. It takes a requirement, prepares a developer-provided Git branch in the selected local repository, analyzes the codebase, uses a coding provider such as Codex to implement the change, and automatically runs repository-specific validation.

The selected local project is the actual development workspace, so AI-generated changes are immediately visible in the developer's normal IDE (for example IntelliJ). The application does not create a separate source-code worktree for local projects.

**Supported local development platforms: macOS and Windows.**

## Iteration 1 scope

This iteration intentionally stops after validation:

```text
OPEN LOCAL PROJECT
      ↓
CREATE JOB / REQUIREMENT + WORKING BRANCH
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

Review agent, human approval, commit/push and PR/MR creation are deliberately deferred to Iteration 2.

## Architecture

```text
Next.js Development AI Agent UI
           ↓ REST + SSE live updates
FastAPI Python backend
           ↓
PostgreSQL job queue + workflow events
           ↓
lease-owned worker subprocess
           ↓
LangGraph + PostgreSQL checkpoint
           ↓
selected local Git project + developer-provided branch
           ↓
repository-aware coding provider (Codex by default)
           ↓
dynamic repository build/test validation
```

The main UI routes are:

- `/dashboard` — home dashboard with projects and workflows
- `/open` — select/register an existing local Git project
- `/board?project=<id>` — project workflow board and requirement creation
- `/board/<job-id>?project=<id>` — job details, events, diff, changed files and validation results

The board receives workflow changes through Server-Sent Events (SSE), allowing running jobs to move through the workflow lanes without waiting for periodic frontend polling.

## Backend capabilities

- FastAPI API
- PostgreSQL persistent jobs, projects, events and worker leases
- LangGraph PostgreSQL checkpointing with `thread_id = job_id`
- async dispatcher + isolated worker processes
- heartbeat/lease based crash recovery
- retry failed jobs from the latest durable checkpoint
- direct operation on the selected local Git repository
- developer-provided working branch created from the configured base branch
- clean-working-tree protection before branch creation
- native local-folder picker on macOS and Windows
- cross-platform command execution without `shell=True`
- Maven wrapper support: `./mvnw` on macOS/Linux and `mvnw.cmd` on Windows
- Gradle wrapper support: `./gradlew` on macOS/Linux and `gradlew.bat` on Windows
- Windows `.cmd` / `.bat` command support for tools such as npm and Codex
- repository analysis for Maven/Gradle/Node/Python/Go/Rust/.NET
- repository instruction discovery (`AGENTS.md`, `CLAUDE.md`, `README.md`, `CONTRIBUTING.md`)
- Codex CLI provider with structured result contract
- provider-independent custom command adapter
- dynamic install/test/build validation
- validation feedback loop back into implementation
- workflow event history and stage timing metrics
- SSE board updates

## Prerequisites

Install these on the same machine where Development AI Agent runs:

- Git
- Python 3.12+
- Node.js + npm
- PostgreSQL
- Codex CLI (when using the default Codex provider)
- Java/Maven/Gradle/etc. as required by the projects that the agent will build and test

Docker is optional. It is only a convenient way to run PostgreSQL locally.

### Windows notes

For native Windows development, install Git for Windows, Python, Node.js and PostgreSQL and ensure their command-line tools are available on `PATH`. Codex CLI should also be installed and authenticated for the Windows user that runs the backend.

A selected repository can use a normal Windows path such as:

```text
C:\Projects\payment-service
```

The application uses the selected Windows folder directly; it does not require WSL or copy the project into a Linux filesystem.

## PostgreSQL

### Option A: Docker

If Docker is available, the simplest setup on either macOS or Windows is:

```bash
docker compose up -d postgres
```

### Option B: native PostgreSQL — macOS

```bash
brew install postgresql@16
brew services start postgresql@16
```

Create the application user and database:

```bash
createuser -s workflow
createdb -O workflow development_workflow
psql -d postgres -c "ALTER USER workflow WITH PASSWORD 'workflow';"
```

### Option C: native PostgreSQL — Windows

Install PostgreSQL using the standard Windows installer and start the PostgreSQL Windows service. If the PostgreSQL `bin` directory is on `PATH`, you can create the same database/user from PowerShell:

```powershell
createuser -U postgres -P workflow
createdb -U postgres -O workflow development_workflow
```

When prompted by `createuser`, use `workflow` as the password. You can also create the `workflow` login and `development_workflow` database with pgAdmin.

Configure `backend/.env` on either platform:

```env
DATABASE_URL=postgresql+psycopg://workflow:workflow@localhost:5432/development_workflow
LANGGRAPH_DATABASE_URL=postgres://workflow:workflow@localhost:5432/development_workflow?sslmode=disable
```

You can also use an existing PostgreSQL server or a managed PostgreSQL instance. Both the application persistence and LangGraph checkpointing require PostgreSQL in the current implementation.

## Backend setup

### macOS

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### Windows PowerShell

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

If PowerShell blocks virtual-environment activation because of the local execution policy, you can either adjust the policy for your user or call the virtual-environment Python executable directly.

API docs are available at `http://localhost:8000/docs`.

The default coding provider is Codex. The machine running the worker must have an authenticated Codex CLI installation available on `PATH`.

Check provider readiness:

```bash
curl http://localhost:8000/api/coding-provider/status
```

On Windows PowerShell you can also open that URL in a browser or use `Invoke-RestMethod`:

```powershell
Invoke-RestMethod http://localhost:8000/api/coding-provider/status
```

## Frontend setup

### macOS

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

### Windows PowerShell

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

Default frontend configuration:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

## Using the UI

1. Open `/open` and select an existing local Git project. The Browse button uses the native folder picker on macOS and Windows.
2. Enter the project board.
3. Create a development job with a title, a new working branch name, and the requirement/acceptance criteria.
4. The backend verifies that the repository working tree is clean and creates the requested branch from the project's base branch.
5. The workflow analyzes the repository and its build/test setup.
6. Codex implements the requirement directly in the selected local project. Changes therefore appear immediately in the developer's IDE.
7. Repository-specific tests/build commands run automatically.
8. Failed validation is supplied back to the implementation agent, up to the configured attempt limit.
9. The board updates live through SSE as the job moves through the workflow stages.
10. Open the job card to inspect event history, changed files, Git diff, stage timings and validation status.
11. In Iteration 1 the developer reviews the resulting files and commits/pushes the branch manually.

## Key configuration

```env
DATABASE_URL=postgresql+psycopg://workflow:workflow@localhost:5432/development_workflow
LANGGRAPH_DATABASE_URL=postgres://workflow:workflow@localhost:5432/development_workflow?sslmode=disable
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

The next iteration will extend the workflow with:

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
