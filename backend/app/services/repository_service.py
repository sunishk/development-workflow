import hashlib
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
    repository_url: str
    base_branch: str


class RepositoryService:
    def prepare_workspace(
        self,
        job_id: UUID,
        repository_url: str,
        base_branch: str = "main",
    ) -> Workspace:
        cache_path = self._cache_path(repository_url)
        workspace_path = self._workspace_path(job_id)
        branch = f"factory/{job_id}"

        self._ensure_roots()
        self._ensure_repository_cache(cache_path, repository_url)
        self._refresh_cache(cache_path)

        if workspace_path.exists():
            self._remove_worktree(cache_path, workspace_path)

        self._run_git(
            [
                "--git-dir",
                str(cache_path),
                "worktree",
                "add",
                "-B",
                branch,
                str(workspace_path),
                f"refs/heads/{base_branch}",
            ]
        )

        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            job.repository_url = repository_url
            job.base_branch = base_branch
            job.workspace_path = str(workspace_path)
            job.workspace_branch = branch
            db.commit()

        event_service.record(
            job_id,
            "WORKSPACE_PREPARED",
            stage="REPOSITORY_PREPARATION",
            message=f"{repository_url} @ {base_branch} -> {branch}",
        )
        return Workspace(job_id, workspace_path, branch, repository_url, base_branch)

    def cleanup_workspace(self, job_id: UUID) -> None:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            repository_url = job.repository_url
            workspace_path_value = job.workspace_path
            workspace_branch = job.workspace_branch

        if not repository_url or not workspace_path_value:
            return

        cache_path = self._cache_path(repository_url)
        workspace_path = self._safe_workspace_path(Path(workspace_path_value))
        self._remove_worktree(cache_path, workspace_path)
        if workspace_branch:
            self._run_git(
                ["--git-dir", str(cache_path), "branch", "-D", workspace_branch],
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
            if not job.repository_url or not job.workspace_path or not job.workspace_branch:
                return None
            return Workspace(
                job_id=job.id,
                path=self._safe_workspace_path(Path(job.workspace_path)),
                branch=job.workspace_branch,
                repository_url=job.repository_url,
                base_branch=job.base_branch or "main",
            )

    def _ensure_repository_cache(self, cache_path: Path, repository_url: str) -> None:
        if cache_path.exists():
            return
        self._run_git(["clone", "--bare", repository_url, str(cache_path)])

    def _refresh_cache(self, cache_path: Path) -> None:
        self._run_git(
            [
                "--git-dir",
                str(cache_path),
                "fetch",
                "--prune",
                "origin",
                "+refs/heads/*:refs/heads/*",
            ]
        )

    def _remove_worktree(self, cache_path: Path, workspace_path: Path) -> None:
        if cache_path.exists():
            self._run_git(
                ["--git-dir", str(cache_path), "worktree", "remove", "--force", str(workspace_path)],
                check=False,
            )
            self._run_git(["--git-dir", str(cache_path), "worktree", "prune"], check=False)
        if workspace_path.exists():
            shutil.rmtree(workspace_path)

    def _cache_path(self, repository_url: str) -> Path:
        digest = hashlib.sha256(repository_url.encode("utf-8")).hexdigest()[:24]
        return Path(settings.repository_cache_root).resolve() / f"{digest}.git"

    def _workspace_path(self, job_id: UUID) -> Path:
        return self._safe_workspace_path(Path(settings.workspace_root) / str(job_id))

    def _safe_workspace_path(self, candidate: Path) -> Path:
        root = Path(settings.workspace_root).resolve()
        resolved = candidate.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError("Workspace path escapes configured workspace root")
        return resolved

    def _ensure_roots(self) -> None:
        Path(settings.repository_cache_root).resolve().mkdir(parents=True, exist_ok=True)
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
