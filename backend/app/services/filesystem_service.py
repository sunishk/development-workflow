from pathlib import Path
from uuid import UUID

from app.services.repository_service import repository_service


class FileSystemService:
    def read_text(self, job_id: UUID, relative_path: str) -> str:
        path = self._resolve(job_id, relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        return path.read_text(encoding="utf-8")

    def write_text(self, job_id: UUID, relative_path: str, content: str) -> None:
        path = self._resolve(job_id, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def list_files(self, job_id: UUID, relative_path: str = ".") -> list[str]:
        root = self._resolve(job_id, relative_path)
        if not root.exists():
            raise FileNotFoundError(relative_path)
        workspace = self._workspace_root(job_id)
        paths = root.rglob("*") if root.is_dir() else [root]
        return sorted(
            str(path.relative_to(workspace))
            for path in paths
            if path.is_file() and ".git" not in path.parts
        )

    def delete(self, job_id: UUID, relative_path: str) -> None:
        path = self._resolve(job_id, relative_path)
        if path.is_dir():
            raise ValueError("Directory deletion is not supported")
        if path.exists():
            path.unlink()

    def _resolve(self, job_id: UUID, relative_path: str) -> Path:
        workspace = self._workspace_root(job_id)
        candidate = (workspace / relative_path).resolve()
        if candidate != workspace and workspace not in candidate.parents:
            raise ValueError("Path escapes job workspace")
        return candidate

    @staticmethod
    def _workspace_root(job_id: UUID) -> Path:
        workspace = repository_service.workspace_for_job(job_id)
        if workspace is None:
            raise ValueError(f"Job {job_id} has no prepared workspace")
        return workspace.path.resolve()


filesystem_service = FileSystemService()
