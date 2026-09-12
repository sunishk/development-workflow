from typing import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


class WorkflowState(TypedDict):
    job_id: str
    title: str
    description: str
    stage: str
    status: str
    requirements: str
    tech_spec: str
    tasks: list[str]


def intake(state: WorkflowState) -> WorkflowState:
    return {**state, "stage": "INTAKE", "status": "RUNNING"}


def requirements(state: WorkflowState) -> WorkflowState:
    return {
        **state,
        "stage": "REQUIREMENTS",
        "requirements": state["description"],
    }


def tech_spec(state: WorkflowState) -> WorkflowState:
    return {
        **state,
        "stage": "TECH_SPEC",
        "tech_spec": f"Technical analysis for: {state['title']}",
    }


def tasks(state: WorkflowState) -> WorkflowState:
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
