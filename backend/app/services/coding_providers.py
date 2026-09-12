import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class ProviderExecutionResult:
    provider: str
    summary: str
    raw_stdout: str
    raw_stderr: str
    returncode: int


class CodingProvider(Protocol):
    name: str

    def execute(self, workspace: Path, payload: dict) -> ProviderExecutionResult:
        ...


class CodexCliProvider:
    name = "codex"

    _OUTPUT_SCHEMA = {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "changed_files", "notes"],
        "properties": {
            "summary": {"type": "string"},
            "changed_files": {
                "type": "array",
                "items": {"type": "string"},
            },
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    }

    def execute(self, workspace: Path, payload: dict) -> ProviderExecutionResult:
        prompt = self._build_prompt(payload)

        with tempfile.TemporaryDirectory(prefix="factory-codex-") as temp_dir:
            temp_path = Path(temp_dir)
            schema_path = temp_path / "output-schema.json"
            output_path = temp_path / "last-message.json"
            schema_path.write_text(json.dumps(self._OUTPUT_SCHEMA), encoding="utf-8")

            command = [
                settings.codex_binary,
                "exec",
                "--json",
                "--ephemeral",
                "--sandbox",
                "workspace-write",
                "--skip-git-repo-check",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
            ]
            if settings.codex_model.strip():
                command.extend(["--model", settings.codex_model.strip()])
            command.append("-")

            try:
                completed = subprocess.run(
                    command,
                    cwd=workspace,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=settings.coding_agent_timeout_seconds,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"Codex CLI executable '{settings.codex_binary}' was not found. Install Codex CLI or configure CODEX_BINARY."
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"Codex coding provider timed out after {settings.coding_agent_timeout_seconds} seconds"
                ) from exc

            if completed.returncode != 0:
                stderr = completed.stderr.strip()[-8000:]
                stdout = completed.stdout.strip()[-8000:]
                detail = stderr or stdout or "No output captured"
                raise RuntimeError(
                    f"Codex coding provider failed with exit code {completed.returncode}: {detail}"
                )

            if not output_path.exists():
                raise RuntimeError("Codex completed without producing the structured final response file")

            raw_message = output_path.read_text(encoding="utf-8").strip()
            try:
                structured = json.loads(raw_message)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Codex returned an invalid structured response: {raw_message[-4000:]}"
                ) from exc

            summary = str(structured.get("summary") or "Codex implementation completed")
            return ProviderExecutionResult(
                provider=self.name,
                summary=summary,
                raw_stdout=completed.stdout,
                raw_stderr=completed.stderr,
                returncode=completed.returncode,
            )

    @staticmethod
    def _build_prompt(payload: dict) -> str:
        return (
            "You are the implementation agent for an automated software factory.\n"
            "Work only inside the current repository workspace.\n"
            "Implement the requested change, update or add tests where appropriate, and follow repository instructions.\n"
            "Do not commit, push, or create pull requests. The orchestration system handles delivery.\n"
            "Do not merely explain what to change: edit the files in the workspace.\n"
            "When validation_feedback is present, use it to fix the previous attempt.\n"
            "Return the structured response required by the supplied output schema.\n\n"
            "WORK ITEM CONTEXT:\n"
            + json.dumps(payload, indent=2)
        )


class CommandProvider:
    name = "command"

    def execute(self, workspace: Path, payload: dict) -> ProviderExecutionResult:
        import shlex

        command = shlex.split(settings.coding_agent_command)
        if not command:
            raise RuntimeError("CODING_AGENT_COMMAND produced an empty command")
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=settings.coding_agent_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Command coding provider timed out after {settings.coding_agent_timeout_seconds} seconds"
            ) from exc

        if completed.returncode != 0:
            detail = completed.stderr.strip()[-8000:] or completed.stdout.strip()[-8000:]
            raise RuntimeError(
                f"Command coding provider failed with exit code {completed.returncode}: {detail}"
            )

        summary = completed.stdout.strip()[-4000:] or "Coding agent completed"
        return ProviderExecutionResult(
            provider=self.name,
            summary=summary,
            raw_stdout=completed.stdout,
            raw_stderr=completed.stderr,
            returncode=completed.returncode,
        )


def build_provider() -> CodingProvider:
    provider = settings.coding_provider.strip().lower()
    if provider == "codex":
        return CodexCliProvider()
    if provider == "command":
        return CommandProvider()
    raise RuntimeError(
        f"Unsupported CODING_PROVIDER '{settings.coding_provider}'. Supported values: codex, command"
    )
