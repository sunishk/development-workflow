import json
import shlex
import subprocess
from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings
from app.services.filesystem_service import filesystem_service
from app.services.repository_analysis_service import RepositoryProfile
from app.services.repository_service import repository_service


@dataclass(frozen=True)
class CodingAgentResult:
    summary: str
    stdout: str
    stderr: str


class CodingAgentService:
    def implement(
        self,
        job_id: UUID,
        *,
        title: str,
        description: str,
        tasks: list[str],
        profile: RepositoryProfile,
        validation_feedback: str | None = None,
    ) -> CodingAgentResult:
        if not settings.coding_agent_command.strip():
            raise RuntimeError(
                "CODING_AGENT_COMMAND is not configured. Configure a coding engine that reads JSON from stdin and edits the current workspace."
            )

        workspace = repository_service.workspace_for_job(job_id)
        if workspace is None:
            raise ValueError(f"Job {job_id} has no prepared workspace")

        instructions: dict[str, str] = {}
        for path in profile.instruction_files:
            try:
                instructions[path] = filesystem_service.read_text(job_id, path)[:20000]
            except (OSError, ValueError):
                continue

        payload = {
            "job_id": str(job_id),
            "title": title,
            "description": description,
            "tasks": tasks,
            "repository_profile": profile.to_dict(),
            "repository_instructions": instructions,
            "validation_feedback": validation_feedback,
        }

        command = shlex.split(settings.coding_agent_command)
        if not command:
            raise RuntimeError("CODING_AGENT_COMMAND produced an empty command")

        completed = subprocess.run(
            command,
            cwd=workspace.path,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=settings.coding_agent_timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Coding agent failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )

        summary = completed.stdout.strip()[-4000:] or "Coding agent completed"
        return CodingAgentResult(summary=summary, stdout=completed.stdout, stderr=completed.stderr)


coding_agent_service = CodingAgentService()
