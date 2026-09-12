import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.services.repository_service import repository_service


@dataclass(frozen=True)
class GitStatus:
    branch: str
    changed_files: list[str]
    clean: bool


class GitService:
    def status(self, job_id: UUID) -> GitStatus:
        workspace = repository_service.workspace_for_job(job_id)
        if workspace is None:
            raise ValueError(f"Job {job_id} has no prepared workspace")

        branch = self._run(workspace.path, ["branch", "--show-current"]).stdout.strip()
        porcelain = self._run(workspace.path, ["status", "--porcelain"]).stdout.splitlines()
        changed_files = [line[3:] for line in porcelain if len(line) >= 4]
        return GitStatus(branch=branch, changed_files=changed_files, clean=not porcelain)

    def diff(self, job_id: UUID) -> str:
        workspace = repository_service.workspace_for_job(job_id)
        if workspace is None:
            raise ValueError(f"Job {job_id} has no prepared workspace")
        return self._run(workspace.path, ["diff", "--no-ext-diff"]).stdout

    def add_all(self, job_id: UUID) -> None:
        workspace = repository_service.workspace_for_job(job_id)
        if workspace is None:
            raise ValueError(f"Job {job_id} has no prepared workspace")
        self._run(workspace.path, ["add", "--all"])

    def commit(self, job_id: UUID, message: str) -> str:
        if not message.strip():
            raise ValueError("Commit message must not be empty")
        workspace = repository_service.workspace_for_job(job_id)
        if workspace is None:
            raise ValueError(f"Job {job_id} has no prepared workspace")
        self._run(workspace.path, ["commit", "-m", message])
        return self._run(workspace.path, ["rev-parse", "HEAD"]).stdout.strip()

    @staticmethod
    def _run(workspace: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.git_command_timeout_seconds,
        )


git_service = GitService()
