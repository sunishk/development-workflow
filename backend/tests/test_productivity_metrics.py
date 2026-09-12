from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.services import productivity_service as productivity_module
from app.services.productivity_service import ProductivityService


class FakeScalars:
    def __init__(self, values):
        self._values = values

    def __iter__(self):
        return iter(self._values)


class FakeSession:
    def __init__(self, job, events):
        self.job = job
        self.events = events

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, model, job_id):
        return self.job

    def scalars(self, statement):
        return FakeScalars(self.events)


def test_job_metrics_aggregates_cycle_queue_execution_and_retry(monkeypatch):
    job_id = uuid4()
    start = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)
    job = SimpleNamespace(
        id=job_id,
        title="Productivity test",
        status="COMPLETED",
        stage="TASKS",
        created_at=start,
    )

    events = [
        SimpleNamespace(event_type="JOB_CREATED", created_at=start, duration_ms=None, stage="CREATED"),
        SimpleNamespace(event_type="JOB_CLAIMED", created_at=start + timedelta(seconds=2), duration_ms=None, stage="CREATED"),
        SimpleNamespace(event_type="TECH_SPEC_FAILED", created_at=start + timedelta(seconds=5), duration_ms=1000.0, stage="TECH_SPEC"),
        SimpleNamespace(event_type="RETRY_QUEUED", created_at=start + timedelta(seconds=6), duration_ms=None, stage="TECH_SPEC"),
        SimpleNamespace(event_type="WORKFLOW_COMPLETED", created_at=start + timedelta(seconds=10), duration_ms=None, stage="TASKS"),
    ]

    monkeypatch.setattr(
        productivity_module,
        "SessionLocal",
        lambda: FakeSession(job, events),
    )
    monkeypatch.setattr(
        productivity_module.event_service,
        "stage_metrics",
        lambda actual_job_id: [
            {
                "stage": "TECH_SPEC",
                "attempts": 2,
                "completed_attempts": 1,
                "failed_attempts": 1,
                "total_duration_ms": 2500.0,
                "last_duration_ms": 1500.0,
            },
            {
                "stage": "TASKS",
                "attempts": 1,
                "completed_attempts": 1,
                "failed_attempts": 0,
                "total_duration_ms": 500.0,
                "last_duration_ms": 500.0,
            },
        ],
    )

    metrics = ProductivityService().job_metrics(job_id)

    assert metrics["cycle_time_ms"] == 10000.0
    assert metrics["queue_wait_ms"] == 2000.0
    assert metrics["execution_time_ms"] == 3000.0
    assert metrics["retry_overhead_ms"] == 1000.0
    assert metrics["retry_count"] == 1
    assert metrics["failed_stage_count"] == 1


def test_latest_failure_is_used_as_terminal_time():
    service = ProductivityService()
    start = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)
    events = [
        SimpleNamespace(event_type="WORKFLOW_FAILED", created_at=start + timedelta(seconds=3)),
        SimpleNamespace(event_type="WORKFLOW_FAILED", created_at=start + timedelta(seconds=8)),
    ]

    assert service._last_event_time(events, "WORKFLOW_FAILED") == start + timedelta(seconds=8)


def test_success_rate_excludes_active_jobs_from_denominator():
    service = ProductivityService()
    assert service._percent(3, 4) == 75.0
    assert service._percent(0, 0) is None
