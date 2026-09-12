from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import filesystem_service as filesystem_module
from app.services import git_service as git_module
from app.services.repository_service import RepositoryService


def test_filesystem_rejects_path_escape(monkeypatch, tmp_path):
    job_id = uuid4()
    workspace = SimpleNamespace(path=tmp_path)
    monkeypatch.setattr(
        filesystem_module.repository_service,
        "workspace_for_job",
        lambda actual_job_id: workspace,
    )

    with pytest.raises(ValueError, match="escapes job workspace"):
        filesystem_module.filesystem_service.read_text(job_id, "../secret.txt")


def test_filesystem_reads_and_writes_inside_workspace(monkeypatch, tmp_path):
    job_id = uuid4()
    workspace = SimpleNamespace(path=tmp_path)
    monkeypatch.setattr(
        filesystem_module.repository_service,
        "workspace_for_job",
        lambda actual_job_id: workspace,
    )

    filesystem_module.filesystem_service.write_text(job_id, "src/App.java", "class App {}")

    assert filesystem_module.filesystem_service.read_text(job_id, "src/App.java") == "class App {}"
    assert filesystem_module.filesystem_service.list_files(job_id) == ["src/App.java"]


def test_git_status_uses_job_workspace(monkeypatch, tmp_path):
    job_id = uuid4()
    workspace = SimpleNamespace(path=tmp_path)
    monkeypatch.setattr(
        git_module.repository_service,
        "workspace_for_job",
        lambda actual_job_id: workspace,
    )

    outputs = {
        ("branch", "--show-current"): "factory/test\n",
        ("status", "--porcelain"): " M src/App.java\n?? src/New.java\n",
    }

    def fake_run(path: Path, args: list[str]):
        return SimpleNamespace(stdout=outputs[tuple(args)])

    monkeypatch.setattr(git_module.git_service, "_run", fake_run)

    status = git_module.git_service.status(job_id)

    assert status.branch == "factory/test"
    assert status.changed_files == ["src/App.java", "src/New.java"]
    assert status.clean is False


def test_repository_workspace_path_is_scoped(monkeypatch, tmp_path):
    service = RepositoryService()
    workspace_root = tmp_path / "workspaces"
    monkeypatch.setattr("app.services.repository_service.settings.workspace_root", str(workspace_root))

    safe = service._workspace_path(uuid4())
    assert safe.parent == workspace_root.resolve()

    with pytest.raises(ValueError, match="escapes configured workspace root"):
        service._safe_workspace_path(tmp_path / "outside")
