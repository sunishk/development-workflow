import shutil
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
    def prepare_workspace(
        self,
        job_id: UUID,
        local_path: str,
        base_branch: str,
    ) -> Workspace:
        source_path = Path(local_path).expanduser().resolve()
        workspace_path = self._workspace_path(job_id)
        branch = f"factory/{job_id}"

        self._ensure_roots()
        self._validate_local_repository(source_path)

        status = self._run_git(["-C", str(source_path), "status", "--porcelain"]).stdout.strip()
        if status:
            raise RuntimeError(
                "Local project has uncommitted changes. Commit or stash them before starting a Software Factory job."
            )

        if workspace_path.exists():
            self._remove_worktree(source_path, workspace_path)

        self._run_git(
            [
                "-C",
                str(source_path),
                "worktree",
                "add",
                "-B",
                branch,
                str(workspace_path),
                base_branch,
            ]
        )

        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            job.local_path = str(source_path)
            job.base_branch = base_branch
            job.workspace_path = str(workspace_path)
            job.workspace_branch = branch
            db.commit()

        event_service.record(
            job_id,
            "WORKSPACE_PREPARED",
            stage="REPOSITORY_PREPARATION",
            message=f"{source_path} @ {base_branch} -> {branch}",
        )
        return Workspace(job_id, workspace_path, branch, str(source_path), base_branch)

    def cleanup_workspace(self, job_id: UUID) -> None:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            local_path = job.local_path
            workspace_path_value = job.workspace_path
            workspace_branch = job.workspace_branch

        if not local_path or not workspace_path_value:
            return

        source_path = Path(local_path).expanduser().resolve()
        workspace_path = self._safe_workspace_path(Path(workspace_path_value))
        self._remove_worktree(source_path, workspace_path)
        if workspace_branch:
            self._run_git(
                ["-C", str(source_path), "branch", "-D", workspace_branch],
                check=False,
            )

        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is not None:
                job.workspace_path = None
                job.workspace_branch = None
                db.commit()

        event_service.record(job_id, "WORKSPACE_CLEANED", stage="REPOSITORY_PREPARATION")

    def workspace_for_job(self, job_id: UUID) -> Workspace | None:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            if not job.local_path or not job.workspace_path or not job.workspace_branch:
                return None
            return Workspace(
                job_id=job.id,
                path=self._safe_workspace_path(Path(job.workspace_path)),
                branch=job.workspace_branch,
                local_path=job.local_path,
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

    def _remove_worktree(self, source_path: Path, workspace_path: Path) -> None:
        if source_path.exists():
            self._run_git(
                ["-C", str(source_path), "worktree", "remove", "--force", str(workspace_path)],
                check=False,
            )
            self._run_git(["-C", str(source_path), "worktree", "prune"], check=False)
        if workspace_path.exists():
            shutil.rmtree(workspace_path)

    def _workspace_path(self, job_id: UUID) -> Path:
        return self._safe_workspace_path(Path(settings.workspace_root) / str(job_id))

    def _safe_workspace_path(self, candidate: Path) -> Path:
        root = Path(settings.workspace_root).resolve()
        resolved = candidate.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError("Workspace path escapes configured workspace root")
        return resolved

    def _ensure_roots(self) -> None:
        Path(settings.workspace_root).resolve().mkdir(parents=True, exist_ok=True)

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
