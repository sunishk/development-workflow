from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.graph.factory_graph import build_graph
from app.graph.test_hooks import failure_controller


@pytest.fixture(autouse=True)
def reset_failure_controller():
    failure_controller.fail_stage = None
    failure_controller.failures_remaining = 0
    yield
    failure_controller.fail_stage = None
    failure_controller.failures_remaining = 0


def initial_state(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "title": "Retry test",
        "description": "Verify workflow recovery",
        "stage": "CREATED",
        "status": "PENDING",
        "requirements": "",
        "tech_spec": "",
        "tasks": [],
        "repository_url": None,
        "base_branch": "main",
        "workspace_path": None,
        "workspace_branch": None,
        "repository_profile": None,
        "implementation_attempts": 0,
        "validation_feedback": None,
        "validation_passed": None,
    }


def test_failed_stage_resumes_from_last_checkpoint():
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer)
    job_id = str(uuid4())
    config = {"configurable": {"thread_id": job_id}}

    failure_controller.fail_stage = "TECH_SPEC"
    failure_controller.failures_remaining = 1

    with pytest.raises(RuntimeError, match="Simulated failure at TECH_SPEC"):
        graph.invoke(initial_state(job_id), config)

    checkpoint = graph.get_state(config)
    assert checkpoint.values["stage"] == "REQUIREMENTS"
    assert checkpoint.values["requirements"] == "Verify workflow recovery"

    result = graph.invoke(None, config)

    assert result["stage"] == "VALIDATE"
    assert result["status"] == "COMPLETED"
    assert result["tech_spec"] == "Technical analysis for: Retry test"
    assert result["tasks"]


def test_retry_uses_same_thread_and_checkpoint():
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer)
    job_id = str(uuid4())
    config = {"configurable": {"thread_id": job_id}}

    failure_controller.fail_stage = "TASKS"
    failure_controller.failures_remaining = 1

    with pytest.raises(RuntimeError, match="Simulated failure at TASKS"):
        graph.invoke(initial_state(job_id), config)

    before_retry = graph.get_state(config)
    assert before_retry.values["stage"] == "TECH_SPEC"
    assert before_retry.values["tech_spec"] == "Technical analysis for: Retry test"

    result = graph.invoke(None, config)

    assert graph.get_state(config).values["job_id"] == job_id
    assert result["stage"] == "VALIDATE"
    assert result["status"] == "COMPLETED"
