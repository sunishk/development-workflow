from time import perf_counter
from typing import Callable, TypedDict
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.graph.test_hooks import failure_controller
from app.services.event_service import event_service


class WorkflowState(TypedDict):
    job_id: str
    title: str
    description: str
    stage: str
    status: str
    requirements: str
    tech_spec: str
    tasks: list[str]


def _run_stage(
    stage: str,
    state: WorkflowState,
    operation: Callable[[WorkflowState], WorkflowState],
) -> WorkflowState:
    job_id = UUID(state["job_id"])
    started = perf_counter()
    event_service.record(job_id, f"{stage}_STARTED", stage=stage)

    try:
        result = operation(state)
    except Exception as exc:
        duration_ms = (perf_counter() - started) * 1000
        event_service.record(
            job_id,
            f"{stage}_FAILED",
            stage=stage,
            message=str(exc),
            duration_ms=duration_ms,
        )
        raise

    duration_ms = (perf_counter() - started) * 1000
    event_service.record(
        job_id,
        f"{stage}_COMPLETED",
        stage=stage,
        duration_ms=duration_ms,
    )
    return result


def _intake(state: WorkflowState) -> WorkflowState:
    if failure_controller.should_fail("INTAKE"):
        raise RuntimeError("Simulated failure at INTAKE")
    return {**state, "stage": "INTAKE", "status": "RUNNING"}


def intake(state: WorkflowState) -> WorkflowState:
    return _run_stage("INTAKE", state, _intake)


def _requirements(state: WorkflowState) -> WorkflowState:
    if failure_controller.should_fail("REQUIREMENTS"):
        raise RuntimeError("Simulated failure at REQUIREMENTS")
    return {
        **state,
        "stage": "REQUIREMENTS",
        "requirements": state["description"],
    }


def requirements(state: WorkflowState) -> WorkflowState:
    return _run_stage("REQUIREMENTS", state, _requirements)


def _tech_spec(state: WorkflowState) -> WorkflowState:
    if failure_controller.should_fail("TECH_SPEC"):
        raise RuntimeError("Simulated failure at TECH_SPEC")
    return {
        **state,
        "stage": "TECH_SPEC",
        "tech_spec": f"Technical analysis for: {state['title']}",
    }


def tech_spec(state: WorkflowState) -> WorkflowState:
    return _run_stage("TECH_SPEC", state, _tech_spec)


def _tasks(state: WorkflowState) -> WorkflowState:
    if failure_controller.should_fail("TASKS"):
        raise RuntimeError("Simulated failure at TASKS")
    return {
        **state,
        "stage": "TASKS",
        "tasks": [
            "Analyze the existing implementation",
            "Implement the required change",
            "Add or update tests",
        ],
        "status": "COMPLETED",
    }


def tasks(state: WorkflowState) -> WorkflowState:
    return _run_stage("TASKS", state, _tasks)


def build_graph(checkpointer: BaseCheckpointSaver):
    graph = StateGraph(WorkflowState)

    graph.add_node("intake", intake)
    graph.add_node("requirements", requirements)
    graph.add_node("tech_spec", tech_spec)
    graph.add_node("tasks", tasks)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "requirements")
    graph.add_edge("requirements", "tech_spec")
    graph.add_edge("tech_spec", "tasks")
    graph.add_edge("tasks", END)

    return graph.compile(checkpointer=checkpointer)
