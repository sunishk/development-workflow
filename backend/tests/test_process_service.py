from pathlib import Path

from app.services import process_service


def test_resolves_local_workspace_executable(tmp_path: Path):
    wrapper = tmp_path / "tool"
    wrapper.write_text("", encoding="utf-8")

    command = process_service.prepare_command(["./tool", "test"], tmp_path)

    assert command == [str(wrapper.resolve()), "test"]


def test_resolves_command_from_path(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(process_service.shutil, "which", lambda executable: "/usr/local/bin/tool")

    command = process_service.prepare_command(["tool", "test"], tmp_path)

    assert command == ["/usr/local/bin/tool", "test"]


def test_wraps_windows_batch_command(monkeypatch, tmp_path: Path):
    wrapper = tmp_path / "mvnw.cmd"
    wrapper.write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr(process_service.os, "name", "nt")
    monkeypatch.setenv("COMSPEC", "cmd.exe")

    command = process_service.prepare_command(["mvnw.cmd", "test"], tmp_path)

    assert command[:4] == ["cmd.exe", "/d", "/s", "/c"]
    assert "mvnw.cmd" in command[4]
    assert "test" in command[4]
