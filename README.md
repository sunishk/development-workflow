# Development Workflow

AI-assisted development workflow built with Python, FastAPI, and LangGraph.

## Architecture

- **FastAPI** — backend API
- **LangGraph** — workflow orchestration
- **PostgreSQL** — persistent application state and production checkpointing
- **Next.js** — frontend (to be added)
- **Jira / GitLab** — planned integrations

## Initial workflow

```text
INTAKE → REQUIREMENTS → TECH_SPEC → TASKS → END
```

The implementation is intentionally incremental. The first milestone establishes the Python/LangGraph foundation before adding repository coding, Jira, GitLab, persistence, approvals, and CI/CD remediation.

## Local development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs are available at `http://localhost:8000/docs`.
