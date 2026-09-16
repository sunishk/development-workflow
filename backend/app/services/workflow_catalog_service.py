from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.services.process_service import prepare_command


@dataclass(frozen=True)
class WorkflowBundle:
    name: str
    repository_url: str
    repository_branch: str
    repository_commit: str
    workflow: str
    skills: dict[str, str]


class WorkflowCatalogService:
    def load(self, name: str) -> WorkflowBundle:
        workflow_name = name.strip()
        if not workflow_name:
            raise ValueError("Workflow name must not be empty")

        repo = self._ensure_repository()
        commit = self._git(repo, ["rev-parse", "HEAD"]).strip()

        workflow_path = repo / "workflows" / f"{workflow_name}.md"
        if not workflow_path.is_file():
            raise ValueError(f"Workflow '{workflow_name}' not found in centralized workflow repository")

        skill_names = [
            "planning-features",
            "implementing-features",
            "reviewing-code",
            "testing-features",
            "coding-guidelines-java",
        ]
        skills: dict[str, str] = {}
        for skill_name in skill_names:
            skill_path = repo / "skills" / skill_name / "SKILL.md"
            if skill_path.is_file():
                skills[skill_name] = skill_path.read_text(encoding="utf-8")

        return WorkflowBundle(
            name=workflow_name,
            repository_url=settings.workflow_repository_url,
            repository_branch=settings.workflow_repository_branch,
            repository_commit=commit,
            workflow=workflow_path.read_text(encoding="utf-8"),
            skills=skills,
        )

    def _ensure_repository(self) -> Path:
        cache_root = Path(settings.workflow_cache_root).expanduser().resolve()
        cache_root.mkdir(parents=True, exist_ok=True)
        repo = cache_root / "skillskit-workflow"

        if not (repo / ".git").exists():
            command = [
                "git",
                "clone",
                "--branch",
                settings.workflow_repository_branch,
                "--single-branch",
                settings.workflow_repository_url,
                str(repo),
            ]
            self._run(command, cache_root)
        else:
            self._run(["git", "fetch", "origin", settings.workflow_repository_branch], repo)
            self._run(["git", "checkout", settings.workflow_repository_branch], repo)
            self._run(["git", "reset", "--hard", f"origin/{settings.workflow_repository_branch}"], repo)

        return repo

    def _git(self, repo: Path, args: list[str]) -> str:
        completed = self._run(["git", *args], repo)
        return completed.stdout

    @staticmethod
    def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                prepare_command(command, cwd),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=settings.git_command_timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Git executable was not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Workflow repository Git command timed out after {settings.git_command_timeout_seconds} seconds"
            ) from exc

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "No output captured"
            raise RuntimeError(f"Workflow repository Git command failed: {detail[-4000:]}")
        return completed


workflow_catalog_service = WorkflowCatalogService()
