import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.services.process_service import prepare_command


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

        # Read Codex's final agent message from its JSONL stdout instead of using
        # --output-last-message. The Windows Codex workspace-write sandbox can
        # deny writes to orchestration-owned output files even when they are
        # placed under the selected repository.
        command = [
            settings.codex_binary,
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
        ]
        if settings.codex_model.strip():
            command.extend(["--model", settings.codex_model.strip()])
        command.append("-")

        try:
            completed = subprocess.run(
                prepare_command(command, workspace),
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

        raw_message = self._extract_final_agent_message(completed.stdout)
        structured = self._parse_structured_response(raw_message)
        summary = str(structured.get("summary") or "Codex implementation completed")
        return ProviderExecutionResult(
            provider=self.name,
            summary=summary,
            raw_stdout=completed.stdout,
            raw_stderr=completed.stderr,
            returncode=completed.returncode,
        )

    @staticmethod
    def _extract_final_agent_message(stdout: str) -> str:
        final_message = ""
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "item.completed":
                continue
            item = event.get("item") or {}
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                final_message = item["text"].strip()

        if not final_message:
            raise RuntimeError(
                "Codex completed without a final agent_message in JSON output"
            )
        return final_message

    @staticmethod
    def _parse_structured_response(raw_message: str) -> dict:
        candidate = raw_message.strip()
        if candidate.startswith("```") and candidate.endswith("```"):
            lines = candidate.splitlines()
            if len(lines) >= 3:
                candidate = "\n".join(lines[1:-1]).strip()

        try:
            structured = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Codex returned an invalid structured response: {raw_message[-4000:]}"
            ) from exc

        if not isinstance(structured, dict):
            raise RuntimeError("Codex structured response must be a JSON object")
        return structured

    @classmethod
    def _build_prompt(cls, payload: dict) -> str:
        return (
            "You are the implementation agent for Development AI Agent.\n"
            "Work only inside the current repository workspace.\n"
            "Implement the requested change, update or add tests where appropriate, and follow repository instructions.\n"
            "Do not commit, push, or create pull requests. The orchestration system handles delivery.\n"
            "Do not merely explain what to change: edit the files in the workspace.\n"
            "When validation_feedback is present, use it to fix the previous attempt.\n"
            "Your FINAL response must contain only one JSON object with no Markdown fences or surrounding text.\n"
            "The JSON object must conform to this schema:\n"
            + json.dumps(cls._OUTPUT_SCHEMA, indent=2)
            + "\n\nWORK ITEM CONTEXT:\n"
            + json.dumps(payload, indent=2)
        )


class CommandProvider:
    name = "command"

    def execute(self, workspace: Path, payload: dict) -> ProviderExecutionResult:
        command = shlex.split(settings.coding_agent_command, posix=os.name != "nt")
        if not command:
            raise RuntimeError("CODING_AGENT_COMMAND produced an empty command")
        try:
            completed = subprocess.run(
                prepare_command(command, workspace),
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
