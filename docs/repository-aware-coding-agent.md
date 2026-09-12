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

## Coding agent contract

`CODING_AGENT_COMMAND` is intentionally provider-agnostic. The command is executed with the job worktree as its current directory. A JSON request is sent on stdin containing:

- job ID
- title and description
- generated tasks
- detected repository profile
- repository instruction file contents
- validation feedback from the previous attempt, when present

The configured coding engine is expected to edit files directly in the current workspace and exit with code 0 when its implementation attempt is complete.

Example shape:

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

This allows the factory to drive any coding engine that can consume the contract, rather than coupling workflow orchestration to a particular LLM vendor.

## Dynamic validation

Validation commands are discovered from repository metadata and executed without shell interpolation. When enabled, dependency installation runs before tests/builds. A failed validation captures stdout/stderr and passes it back to the next implementation attempt.

Configuration:

```text
WORKSPACE_COMMAND_TIMEOUT_SECONDS=900
CODING_AGENT_COMMAND=
CODING_AGENT_TIMEOUT_SECONDS=1800
MAX_IMPLEMENTATION_ATTEMPTS=3
RUN_INSTALL_BEFORE_VALIDATION=true
```

If a repository job reaches `IMPLEMENT` without `CODING_AGENT_COMMAND`, it fails clearly rather than reporting a false success.

## Current boundary

This milestone ends after successful validation. AI review, human approval, commit/push, and PR/MR creation belong to subsequent milestones.
