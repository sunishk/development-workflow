# Repository Workspaces and Git Tools

This milestone adds isolated repository workspaces for workflow jobs.

## Workflow

```text
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
END
```

When a job includes a `repository_url`, the repository preparation stage creates an isolated Git worktree for that job.

## Create a repository-backed job

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Implement payment validation",
    "description": "Add validation to the payment flow",
    "repository_url": "git@github.com:example/payment-service.git",
    "base_branch": "main"
  }'
```

The job stores:

```text
repository_url
base_branch
workspace_path
workspace_branch
```

The generated branch is:

```text
factory/<job-id>
```

## Repository cache

Repositories are cloned once as bare repositories below:

```text
.factory/repositories/
```

The cache key is derived from a SHA-256 hash of the repository URL. Before a workspace is created, the bare cache fetches the current remote branch refs.

## Job worktrees

Each job gets a separate worktree below:

```text
.factory/workspaces/<job-id>/
```

This prevents two jobs from editing the same checked-out files.

## Workspace inspection API

```text
GET    /api/jobs/{job_id}/workspace
GET    /api/jobs/{job_id}/workspace/status
GET    /api/jobs/{job_id}/workspace/files
GET    /api/jobs/{job_id}/workspace/file?path=...
GET    /api/jobs/{job_id}/workspace/diff
DELETE /api/jobs/{job_id}/workspace
```

The cleanup endpoint removes the worktree and its local `factory/<job-id>` branch from the repository cache.

## Tool services

### RepositoryService

Responsibilities:

- maintain bare repository caches
- fetch the current remote branches
- create one worktree per job
- persist workspace metadata
- clean up worktrees

### GitService

Current operations:

- status
- diff
- stage all changes
- commit changes

Commands are executed with argument arrays and `shell=False` behavior through `subprocess.run`; job data is never interpolated into a shell command.

### FileSystemService

Current operations:

- read UTF-8 text files
- write UTF-8 text files
- list files
- delete individual files

Every requested file path is resolved and checked against the job workspace root. Paths such as `../secret.txt` are rejected.

## Authentication

This milestone does not persist repository credentials in workflow jobs.

Private repository access uses Git authentication already configured on the worker host, for example:

- SSH keys / SSH agent
- Git credential helper
- environment-specific Git credential configuration

A later GitHub/GitLab integration milestone should provide managed application credentials rather than storing personal tokens in job records.

## Configuration

```text
REPOSITORY_CACHE_ROOT=.factory/repositories
WORKSPACE_ROOT=.factory/workspaces
GIT_COMMAND_TIMEOUT_SECONDS=120
```

Both directories are ignored by Git in this repository.

## Next milestone

The repository workspace is the execution boundary for the coding agent. The next stage can safely inspect and edit a Spring Boot project, run Maven tests/builds, examine Git diffs, and iterate without changing the main checkout.
