import sys
from uuid import uuid4

from app import worker
from app.services import worker_manager as worker_manager_module
from app.services.worker_manager import WorkerManager


def test_worker_manager_spawns_separate_python_process(monkeypatch):
    calls = {}

    class FakeProcess:
        returncode = None

        def poll(self):
            return None

    def fake_popen(command, cwd):
        calls["command"] = command
        calls["cwd"] = cwd
        return FakeProcess()

    monkeypatch.setattr(worker_manager_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(worker_manager_module.settings, "worker_cwd", ".")

    manager = WorkerManager()
    job_id = uuid4()
    manager._spawn_worker(job_id)

    assert calls["command"] == [
        sys.executable,
        "-m",
        "app.worker",
        str(job_id),
    ]
    assert calls["cwd"] == "."
    assert job_id in manager._processes


def test_worker_executes_job_with_same_job_id(monkeypatch):
    job_id = uuid4()
    calls = []

    monkeypatch.setattr(sys, "argv", ["app.worker", str(job_id)])
    monkeypatch.setattr(worker.workflow_service, "start", lambda: calls.append("start"))
    monkeypatch.setattr(
        worker.workflow_service,
        "execute",
        lambda actual_job_id: calls.append(("execute", actual_job_id)),
    )
    monkeypatch.setattr(worker.workflow_service, "stop", lambda: calls.append("stop"))
    monkeypatch.setattr(
        worker.checkpointer_manager,
        "stop",
        lambda: calls.append("checkpointer-stop"),
    )

    assert worker.main() == 0
    assert calls == [
        "start",
        ("execute", job_id),
        "stop",
        "checkpointer-stop",
    ]
