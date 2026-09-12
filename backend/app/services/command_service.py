import subprocess
from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings
from app.services.process_service import prepare_command
from app.services.repository_service import repository_service


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    return_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0


class CommandService:
    def run(self, job_id: UUID, command: list[str], *, check: bool = False) -> CommandResult:
        if not command or any(not part for part in command):
            raise ValueError("Command must contain non-empty arguments")

        workspace = repository_service.workspace_for_job(job_id)
        if workspace is None:
            raise ValueError(f"Job {job_id} has no prepared workspace")

        executable_command = prepare_command(command, workspace.path)
        completed = subprocess.run(
            executable_command,
            cwd=workspace.path,
            check=False,
            capture_output=True,
            text=True,
            timeout=settings.workspace_command_timeout_seconds,
        )
        result = CommandResult(
            command=command,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and not result.succeeded:
            raise RuntimeError(
                f"Command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr[-4000:]}"
            )
        return result


command_service = CommandService()
