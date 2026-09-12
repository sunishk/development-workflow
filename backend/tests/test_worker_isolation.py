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
    monkeypatch.setattr(worker_manager_module.event_service, "record", lambda *args, **kwargs: None)

    manager = WorkerManager()
    job_id = uuid4()
    worker_id = str(uuid4())
    manager._spawn_worker(job_id, worker_id)

    assert calls["command"] == [
        sys.executable,
        "-m",
        "app.worker",
        str(job_id),
        worker_id,
    ]
    assert calls["cwd"] == "."
    assert job_id in manager._processes


def test_worker_executes_job_with_same_job_and_worker_id(monkeypatch):
    job_id = uuid4()
    worker_id = str(uuid4())
    calls = []

    class FakeHeartbeat:
        def __init__(self, actual_job_id, actual_worker_id):
            calls.append(("heartbeat-init", actual_job_id, actual_worker_id))

        def start(self):
            calls.append("heartbeat-start")

        def stop(self):
            calls.append("heartbeat-stop")

    monkeypatch.setattr(sys, "argv", ["app.worker", str(job_id), worker_id])
    monkeypatch.setattr(worker, "HeartbeatService", FakeHeartbeat)
    monkeypatch.setattr(worker.workflow_service, "start", lambda: calls.append("start"))
    monkeypatch.setattr(
        worker.workflow_service,
        "execute",
        lambda actual_job_id, actual_worker_id: calls.append(
            ("execute", actual_job_id, actual_worker_id)
        ),
    )
    monkeypatch.setattr(worker.workflow_service, "stop", lambda: calls.append("stop"))
    monkeypatch.setattr(
        worker.checkpointer_manager,
        "stop",
        lambda: calls.append("checkpointer-stop"),
    )

    assert worker.main() == 0
    assert calls == [
        ("heartbeat-init", job_id, worker_id),
        "start",
        "heartbeat-start",
        ("execute", job_id, worker_id),
        "heartbeat-stop",
        "stop",
        "checkpointer-stop",
    ]
