from time import perf_counter
from typing import Callable, TypedDict
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.graph.test_hooks import failure_controller
from app.services.coding_agent_service import coding_agent_service
from app.services.command_service import command_service
from app.services.event_service import event_service
from app.services.repository_analysis_service import RepositoryProfile, repository_analysis_service
from app.services.repository_service import repository_service


class WorkflowState(TypedDict):
    job_id: str
    title: str
    description: str
    stage: str
    status: str
    requirements: str
    tech_spec: str
    tasks: list[str]
    local_path: str | None
    base_branch: str
    workspace_path: str | None
    workspace_branch: str | None
    repository_profile: dict | None
    implementation_attempts: int
    validation_feedback: str | None
    validation_passed: bool | None


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
    return {**state, "stage": "REQUIREMENTS", "requirements": state["description"]}


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
    }


def tasks(state: WorkflowState) -> WorkflowState:
    return _run_stage("TASKS", state, _tasks)


def _repository_preparation(state: WorkflowState) -> WorkflowState:
    if failure_controller.should_fail("REPOSITORY_PREPARATION"):
        raise RuntimeError("Simulated failure at REPOSITORY_PREPARATION")

    local_path = state.get("local_path")
    if not local_path:
        raise RuntimeError("Local project path is missing")

    working_branch = state.get("workspace_branch")
    if not working_branch:
        raise RuntimeError("Working branch is missing")

    workspace = repository_service.prepare_workspace(
        UUID(state["job_id"]),
        local_path,
        state.get("base_branch") or "main",
        working_branch,
    )
    return {
        **state,
        "stage": "REPOSITORY_PREPARATION",
        "workspace_path": str(workspace.path),
        "workspace_branch": workspace.branch,
    }


def repository_preparation(state: WorkflowState) -> WorkflowState:
    return _run_stage("REPOSITORY_PREPARATION", state, _repository_preparation)


def _repository_analysis(state: WorkflowState) -> WorkflowState:
    profile = repository_analysis_service.analyze(UUID(state["job_id"]))
    return {
        **state,
        "stage": "REPOSITORY_ANALYSIS",
        "repository_profile": profile.to_dict(),
    }


def repository_analysis(state: WorkflowState) -> WorkflowState:
    return _run_stage("REPOSITORY_ANALYSIS", state, _repository_analysis)


def _implement(state: WorkflowState) -> WorkflowState:
    profile_data = state.get("repository_profile")
    if not profile_data:
        raise RuntimeError("Repository profile is missing")

    profile = RepositoryProfile(**profile_data)
    attempt = int(state.get("implementation_attempts") or 0) + 1
    coding_agent_service.implement(
        UUID(state["job_id"]),
        title=state["title"],
        description=state["description"],
        tasks=state["tasks"],
        profile=profile,
        validation_feedback=state.get("validation_feedback"),
    )
    return {
        **state,
        "stage": "IMPLEMENT",
        "implementation_attempts": attempt,
        "validation_passed": None,
    }


def implement(state: WorkflowState) -> WorkflowState:
    return _run_stage("IMPLEMENT", state, _implement)


def _validate(state: WorkflowState) -> WorkflowState:
    # Re-analyse after implementation because the coding agent may bootstrap a
    # build system (for example, create pom.xml in an initially minimal repo).
    refreshed_profile = repository_analysis_service.analyze(UUID(state["job_id"]))
    profile = refreshed_profile

    commands: list[list[str]] = []
    if settings.run_install_before_validation and profile.install_command:
        commands.append(profile.install_command)
    if profile.test_command:
        commands.append(profile.test_command)
    if profile.build_command:
        commands.append(profile.build_command)

    if not commands:
        raise RuntimeError("No validation command could be detected for this repository")

    failures: list[str] = []
    for command in commands:
        result = command_service.run(UUID(state["job_id"]), command)
        if not result.succeeded:
            failures.append(
                f"$ {' '.join(command)}\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}"
            )
            break

    if failures:
        feedback = "\n".join(failures)
        attempts = int(state.get("implementation_attempts") or 0)
        if attempts >= settings.max_implementation_attempts:
            raise RuntimeError(
                f"Validation failed after {attempts} implementation attempts:\n{feedback}"
            )
        return {
            **state,
            "stage": "VALIDATE",
            "repository_profile": refreshed_profile.to_dict(),
            "validation_feedback": feedback,
            "validation_passed": False,
        }

    return {
        **state,
        "stage": "VALIDATE",
        "repository_profile": refreshed_profile.to_dict(),
        "validation_feedback": None,
        "validation_passed": True,
        "status": "COMPLETED",
    }


def validate(state: WorkflowState) -> WorkflowState:
    return _run_stage("VALIDATE", state, _validate)


def _after_validate(state: WorkflowState) -> str:
    return "end" if state.get("validation_passed") else "implement"


def build_graph(checkpointer: BaseCheckpointSaver):
    graph = StateGraph(WorkflowState)

    graph.add_node("intake", intake)
    graph.add_node("requirements", requirements)
    graph.add_node("tech_spec", tech_spec)
    graph.add_node("tasks", tasks)
    graph.add_node("repository_preparation", repository_preparation)
    graph.add_node("repository_analysis", repository_analysis)
    graph.add_node("implement", implement)
    graph.add_node("validate", validate)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "requirements")
    graph.add_edge("requirements", "tech_spec")
    graph.add_edge("tech_spec", "tasks")
    graph.add_edge("tasks", "repository_preparation")
    graph.add_edge("repository_preparation", "repository_analysis")
    graph.add_edge("repository_analysis", "implement")
    graph.add_edge("implement", "validate")
    graph.add_conditional_edges("validate", _after_validate, {"implement": "implement", "end": END})

    return graph.compile(checkpointer=checkpointer)
