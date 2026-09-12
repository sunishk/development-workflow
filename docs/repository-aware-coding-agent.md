# Repository-Aware Coding Agent

The workflow is technology-agnostic. A target repository is analyzed after its per-job workspace is prepared, then the detected project profile drives implementation and validation.

## Workflow

```text
INTAKE
  -> REQUIREMENTS
  -> TECH_SPEC
  -> TASKS
  -> REPOSITORY_PREPARATION
  -> REPOSITORY_ANALYSIS
  -> IMPLEMENT
  -> VALIDATE
       | pass -> END
       | fail -> IMPLEMENT (up to MAX_IMPLEMENTATION_ATTEMPTS)
```

## Repository analysis

The analyzer currently recognizes common repository markers and derives commands from the project itself:

- Maven / Spring Boot: `pom.xml`, optional `mvnw`
- Gradle: `build.gradle`, `build.gradle.kts`, optional `gradlew`
- Node.js / TypeScript / React / Next.js: `package.json` plus lockfiles and scripts
- Python: `pyproject.toml`, `requirements.txt`
- Go: `go.mod`
- Rust: `Cargo.toml`
- .NET: `.csproj`, `.sln`

It also discovers repository instruction files such as `AGENTS.md`, `CLAUDE.md`, `README.md`, and `CONTRIBUTING.md`.

## Concrete coding provider

`CODING_PROVIDER=codex` is now the default concrete implementation provider. The worker invokes Codex CLI headlessly inside the isolated job worktree using `codex exec` with JSONL output, an ephemeral session, `workspace-write` sandboxing, and a JSON output schema.

Codex receives the work item and repository profile on stdin and is instructed to edit files directly in the current worktree. It must not commit, push, or create a PR/MR; those actions remain the responsibility of later workflow stages.

The final Codex response is schema-constrained to:

```json
{
  "summary": "Implemented the requested change",
  "changed_files": ["src/example.py"],
  "notes": ["Added unit tests"]
}
```

The provider adapter normalizes missing executable, timeout, non-zero exit, invalid structured output, stdout, and stderr into actionable workflow failures.

### Codex setup

Install and authenticate Codex CLI on the same machine/container that runs workflow workers. The worker inherits that Codex authentication context.

```text
CODING_PROVIDER=codex
CODEX_BINARY=codex
CODEX_MODEL=
CODING_AGENT_TIMEOUT_SECONDS=1800
```

`CODEX_MODEL` can be left empty to use the CLI's configured/default model. Set it only when the deployment needs to pin a model.

## Generic command provider

The previous provider-agnostic command contract remains available:

```text
CODING_PROVIDER=command
CODING_AGENT_COMMAND=/path/to/custom-coding-agent
```

The custom command is executed with the job worktree as its current directory and receives JSON on stdin containing:

- job ID
- title and description
- generated tasks
- detected repository profile
- repository instruction file contents
- validation feedback from the previous attempt, when present

Example input shape:

```json
{
  "job_id": "...",
  "title": "Add validation",
  "description": "...",
  "tasks": ["..."],
  "repository_profile": {
    "languages": ["TypeScript"],
    "frameworks": ["Next.js", "React"],
    "package_manager": "npm",
    "install_command": ["npm", "ci"],
    "test_command": ["npm", "run", "test"],
    "build_command": ["npm", "run", "build"]
  },
  "validation_feedback": null
}
```

This keeps workflow orchestration independent of one vendor even though Codex is the first built-in provider.

## Dynamic validation

Validation commands are discovered from repository metadata and executed without shell interpolation. When enabled, dependency installation runs before tests/builds. A failed validation captures stdout/stderr and passes it back to the next implementation attempt.

Configuration:

```text
WORKSPACE_COMMAND_TIMEOUT_SECONDS=900
CODING_PROVIDER=codex
CODING_AGENT_COMMAND=
CODING_AGENT_TIMEOUT_SECONDS=1800
CODEX_BINARY=codex
CODEX_MODEL=
MAX_IMPLEMENTATION_ATTEMPTS=3
RUN_INSTALL_BEFORE_VALIDATION=true
```

With the default `codex` provider, repository-backed jobs can proceed through a real implementation attempt as long as Codex CLI is installed and authenticated in the worker environment.

## Current boundary

This milestone ends after successful validation. AI review, human approval, commit/push, and PR/MR creation belong to subsequent milestones.
