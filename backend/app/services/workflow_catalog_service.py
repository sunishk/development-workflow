from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.services.process_service import prepare_command


@dataclass(frozen=True)
class WorkflowBundle:
    name: str
    stage: str
    repository_url: str
    repository_branch: str
    repository_commit: str
    skills: dict[str, str]


class WorkflowCatalogService:
    def load(self, name: str, stage: str) -> WorkflowBundle:
        workflow_name = name.strip()
        workflow_stage = stage.strip().upper()
        if not workflow_name:
            raise ValueError("Workflow name must not be empty")
        if not workflow_stage:
            raise ValueError("Workflow stage must not be empty")

        repo = self._ensure_repository()
        commit = self._git(repo, ["rev-parse", "HEAD"]).strip()
        workflow_path = repo / "workflows" / f"{workflow_name}.md"
        if not workflow_path.is_file():
            raise ValueError(f"Workflow '{workflow_name}' not found in centralized workflow repository")

        # Parse workflow metadata locally and send the LLM only the instructions
        # needed for the current stage. The full orchestrator is not put into
        # every provider prompt.
        workflow_text = workflow_path.read_text(encoding="utf-8")
        skill_paths = self._skill_paths_for_stage(workflow_text, workflow_stage)
        skills: dict[str, str] = {}
        for relative_path in skill_paths:
            skill_path = repo / relative_path
            if not skill_path.is_file():
                raise ValueError(f"Workflow '{workflow_name}' references missing skill '{relative_path}'")
            skills[relative_path] = skill_path.read_text(encoding="utf-8")

        return WorkflowBundle(
            name=workflow_name,
            stage=workflow_stage,
            repository_url=settings.workflow_repository_url,
            repository_branch=settings.workflow_repository_branch,
            repository_commit=commit,
            skills=skills,
        )

    @staticmethod
    def _skill_paths_for_stage(workflow_text: str, stage: str) -> list[str]:
        aliases = {
            "IMPLEMENT": "Implementation",
            "IMPLEMENTATION": "Implementation",
            "PLANNING": "Planning",
            "REVIEW": "Review",
            "TEST": "Testing",
            "TESTING": "Testing",
        }
        mapping_name = aliases.get(stage, stage.title())
        paths: list[str] = []
        for line in workflow_text.splitlines():
            match = re.match(r"\s*-\s*([^:]+):\s*`([^`]+)`\s*$", line)
            if not match:
                continue
            label, path = match.groups()
            label = label.strip()
            if label.casefold() == mapping_name.casefold():
                paths.append(path.strip())
            elif stage in {"IMPLEMENT", "IMPLEMENTATION", "REVIEW", "TEST", "TESTING"} and (
                "standard" in label.casefold() or "guideline" in label.casefold()
            ):
                paths.append(path.strip())

        if not paths:
            raise ValueError(f"No skills mapped for stage '{stage}' in workflow")
        return list(dict.fromkeys(paths))

    def _ensure_repository(self) -> Path:
        cache_root = Path(settings.workflow_cache_root).expanduser().resolve()
        cache_root.mkdir(parents=True, exist_ok=True)
        repo = cache_root / "skillskit-workflow"

        if not (repo / ".git").exists():
            self._run([
                "git", "clone", "--branch", settings.workflow_repository_branch,
                "--single-branch", settings.workflow_repository_url, str(repo),
            ], cache_root)
        else:
            self._run(["git", "fetch", "origin", settings.workflow_repository_branch], repo)
            self._run(["git", "checkout", settings.workflow_repository_branch], repo)
            self._run(["git", "reset", "--hard", f"origin/{settings.workflow_repository_branch}"], repo)
        return repo

    def _git(self, repo: Path, args: list[str]) -> str:
        return self._run(["git", *args], repo).stdout

    @staticmethod
    def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                prepare_command(command, cwd), cwd=cwd, capture_output=True, text=True,
                timeout=settings.git_command_timeout_seconds, check=False,
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
