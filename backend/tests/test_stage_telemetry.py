from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.graph import factory_graph
from app.services.event_service import event_service


def _state() -> factory_graph.WorkflowState:
    return {
        "job_id": str(uuid4()),
        "title": "Telemetry test",
        "description": "Measure workflow stages",
        "stage": "CREATED",
        "status": "PENDING",
        "requirements": "",
        "tech_spec": "",
        "tasks": [],
    }


def test_stage_records_started_and_completed_with_duration(monkeypatch):
    events = []

    monkeypatch.setattr(
        factory_graph.event_service,
        "record",
        lambda job_id, event_type, **kwargs: events.append((event_type, kwargs)),
    )
    monkeypatch.setattr(factory_graph.failure_controller, "should_fail", lambda stage: False)

    result = factory_graph.tech_spec(_state())

    assert result["stage"] == "TECH_SPEC"
    assert [event[0] for event in events] == ["TECH_SPEC_STARTED", "TECH_SPEC_COMPLETED"]
    assert events[1][1]["duration_ms"] >= 0


def test_failed_stage_records_failed_attempt_duration(monkeypatch):
    events = []

    monkeypatch.setattr(
        factory_graph.event_service,
        "record",
        lambda job_id, event_type, **kwargs: events.append((event_type, kwargs)),
    )
    monkeypatch.setattr(
        factory_graph.failure_controller,
        "should_fail",
        lambda stage: stage == "REQUIREMENTS",
    )

    with pytest.raises(RuntimeError, match="Simulated failure at REQUIREMENTS"):
        factory_graph.requirements(_state())

    assert [event[0] for event in events] == ["REQUIREMENTS_STARTED", "REQUIREMENTS_FAILED"]
    assert events[1][1]["duration_ms"] >= 0
    assert events[1][1]["message"] == "Simulated failure at REQUIREMENTS"


def test_stage_metrics_aggregate_failed_and_successful_retry(monkeypatch):
    events = [
        SimpleNamespace(stage="TECH_SPEC", event_type="TECH_SPEC_STARTED", duration_ms=None),
        SimpleNamespace(stage="TECH_SPEC", event_type="TECH_SPEC_FAILED", duration_ms=1200.0),
        SimpleNamespace(stage="TECH_SPEC", event_type="TECH_SPEC_STARTED", duration_ms=None),
        SimpleNamespace(stage="TECH_SPEC", event_type="TECH_SPEC_COMPLETED", duration_ms=800.5),
    ]
    monkeypatch.setattr(event_service, "list_for_job", lambda job_id: events)

    metrics = event_service.stage_metrics(uuid4())

    assert metrics == [
        {
            "stage": "TECH_SPEC",
            "attempts": 2,
            "completed_attempts": 1,
            "failed_attempts": 1,
            "total_duration_ms": 2000.5,
            "last_duration_ms": 800.5,
        }
    ]
