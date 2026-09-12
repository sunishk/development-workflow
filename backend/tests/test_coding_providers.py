import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import coding_providers


def test_build_provider_defaults_to_codex(monkeypatch):
    monkeypatch.setattr(coding_providers.settings, "coding_provider", "codex")
    provider = coding_providers.build_provider()
    assert isinstance(provider, coding_providers.CodexCliProvider)


def test_codex_provider_invokes_exec_with_structured_output(monkeypatch, tmp_path):
    calls = {}

    def fake_run(command, cwd, input, capture_output, text, timeout, check):
        calls["command"] = command
        calls["cwd"] = cwd
        calls["input"] = input
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(
            json.dumps(
                {
                    "summary": "Implemented feature",
                    "changed_files": ["src/app.py"],
                    "notes": ["tests updated"],
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout='{"type":"turn.completed"}\n', stderr="")

    monkeypatch.setattr(coding_providers.subprocess, "run", fake_run)
    monkeypatch.setattr(coding_providers.settings, "codex_binary", "codex")
    monkeypatch.setattr(coding_providers.settings, "codex_model", "")
    monkeypatch.setattr(coding_providers.settings, "coding_agent_timeout_seconds", 30)

    result = coding_providers.CodexCliProvider().execute(
        tmp_path,
        {"title": "Add endpoint", "validation_feedback": None},
    )

    assert result.provider == "codex"
    assert result.summary == "Implemented feature"
    assert calls["cwd"] == tmp_path
    assert calls["command"][:3] == ["codex", "exec", "--json"]
    assert "--sandbox" in calls["command"]
    assert "workspace-write" in calls["command"]
    assert "--output-schema" in calls["command"]
    assert calls["command"][-1] == "-"
    assert "Add endpoint" in calls["input"]


def test_codex_provider_reports_missing_binary(monkeypatch, tmp_path):
    def missing(*args, **kwargs):
        raise FileNotFoundError("codex")

    monkeypatch.setattr(coding_providers.subprocess, "run", missing)
    monkeypatch.setattr(coding_providers.settings, "codex_binary", "codex")

    with pytest.raises(RuntimeError, match="Codex CLI executable 'codex' was not found"):
        coding_providers.CodexCliProvider().execute(tmp_path, {"title": "test"})


def test_codex_provider_reports_timeout(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise coding_providers.subprocess.TimeoutExpired(cmd="codex", timeout=12)

    monkeypatch.setattr(coding_providers.subprocess, "run", timeout)
    monkeypatch.setattr(coding_providers.settings, "coding_agent_timeout_seconds", 12)

    with pytest.raises(RuntimeError, match="timed out after 12 seconds"):
        coding_providers.CodexCliProvider().execute(tmp_path, {"title": "test"})


def test_codex_provider_reports_nonzero_exit(monkeypatch, tmp_path):
    monkeypatch.setattr(
        coding_providers.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=7,
            stdout="",
            stderr="authentication failed",
        ),
    )

    with pytest.raises(RuntimeError, match="exit code 7: authentication failed"):
        coding_providers.CodexCliProvider().execute(tmp_path, {"title": "test"})
