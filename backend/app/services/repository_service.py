import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.db import Job, SessionLocal
from app.services.event_service import event_service


@dataclass(frozen=True)
class Workspace:
    job_id: UUID
    path: Path
    branch: str
    local_path: str
    base_branch: str


class RepositoryService:
    def validate_working_branch(self, local_path: str, working_branch: str) -> str:
        source_path = Path(local_path).expanduser().resolve()
        branch = working_branch.strip()

        self._validate_local_repository(source_path)
        if not branch:
            raise ValueError("Working branch is required")

        branch_check = self._run_git(
            ["check-ref-format", "--branch", branch],
            check=False,
        )
        if branch_check.returncode != 0:
            raise ValueError(f"Invalid Git branch name: {branch}")

        branch_exists = (
            self._run_git(
                ["-C", str(source_path), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
                check=False,
            ).returncode
            == 0
        )
        if branch_exists:
            raise RuntimeError(
                f"Branch '{branch}' already exists. Choose a new branch name for this development job."
            )

        return branch

    def prepare_workspace(
        self,
        job_id: UUID,
        local_path: str,
        base_branch: str,
        working_branch: str,
    ) -> Workspace:
        source_path = Path(local_path).expanduser().resolve()
        branch = self.validate_working_branch(local_path, working_branch)

        status = self._run_git(["-C", str(source_path), "status", "--porcelain"]).stdout.strip()
        if status:
            raise RuntimeError(
                "Local project has uncommitted changes. Commit or stash them before starting a Development AI Agent job."
            )

        current_branch = self._run_git(
            ["-C", str(source_path), "branch", "--show-current"]
        ).stdout.strip()
        if not current_branch:
            raise RuntimeError("Detached HEAD is not supported; checkout a branch first")

        base_exists = (
            self._run_git(
                ["-C", str(source_path), "show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"],
                check=False,
            ).returncode
            == 0
        )
        if not base_exists:
            raise RuntimeError(f"Base branch '{base_branch}' does not exist in the local repository")

        self._run_git(
            ["-C", str(source_path), "switch", "-c", branch, base_branch]
        )

        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            job.local_path = str(source_path)
            job.base_branch = base_branch
            job.workspace_path = str(source_path)
            job.workspace_branch = branch
            db.commit()

        event_service.record(
            job_id,
            "WORKSPACE_PREPARED",
            stage="REPOSITORY_PREPARATION",
            message=f"Using local project directly: {source_path} on {branch} (from {base_branch})",
        )
        return Workspace(job_id, source_path, branch, str(source_path), base_branch)

    def cleanup_workspace(self, job_id: UUID) -> None:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")

        # Local-project mode intentionally leaves the developer's selected folder,
        # branch, and uncommitted agent changes untouched for manual review/commit.
        event_service.record(
            job_id,
            "WORKSPACE_CLEANUP_SKIPPED",
            stage="REPOSITORY_PREPARATION",
            message="Local project is the active workspace; files and branch were left unchanged",
        )

    def workspace_for_job(self, job_id: UUID) -> Workspace | None:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            if not job.local_path or not job.workspace_path or not job.workspace_branch:
                return None

            workspace_path = Path(job.workspace_path).expanduser().resolve()
            local_path = Path(job.local_path).expanduser().resolve()
            if workspace_path != local_path:
                raise ValueError("Job workspace does not match the selected local project")

            return Workspace(
                job_id=job.id,
                path=workspace_path,
                branch=job.workspace_branch,
                local_path=str(local_path),
                base_branch=job.base_branch or "main",
            )

    def _validate_local_repository(self, source_path: Path) -> None:
        if not source_path.exists() or not source_path.is_dir():
            raise ValueError(f"Local project path does not exist: {source_path}")
        try:
            root = self._run_git(
                ["-C", str(source_path), "rev-parse", "--show-toplevel"]
            ).stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"Local project is not a Git repository: {source_path}") from exc
        if Path(root).resolve() != source_path:
            raise ValueError(f"Select the Git repository root folder: {root}")

    @staticmethod
    def _run_git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            check=check,
            capture_output=True,
            text=True,
            timeout=settings.git_command_timeout_seconds,
        )


repository_service = RepositoryService()
