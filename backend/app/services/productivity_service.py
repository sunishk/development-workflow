from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.db import Job, SessionLocal, WorkflowEvent
from app.services.event_service import event_service


TERMINAL_STATUSES = {"COMPLETED", "FAILED"}
STAGE_TERMINAL_SUFFIXES = ("_COMPLETED", "_FAILED")


class ProductivityService:
    def job_metrics(self, job_id: UUID) -> dict:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")

            events = list(
                db.scalars(
                    select(WorkflowEvent)
                    .where(WorkflowEvent.job_id == job_id)
                    .order_by(WorkflowEvent.created_at, WorkflowEvent.id)
                )
            )

        created_at = self._event_time(events, "JOB_CREATED") or job.created_at
        first_claimed_at = self._event_time(events, "JOB_CLAIMED")
        completed_at = self._event_time(events, "WORKFLOW_COMPLETED")
        failed_at = self._event_time(events, "WORKFLOW_FAILED")
        terminal_at = completed_at or (failed_at if job.status == "FAILED" else None)
        effective_end = terminal_at or datetime.now(timezone.utc)

        stage_metrics = event_service.stage_metrics(job_id)
        execution_time_ms = round(
            sum(float(metric["total_duration_ms"]) for metric in stage_metrics), 3
        )

        retry_overhead_ms = round(
            sum(
                float(event.duration_ms or 0.0)
                for event in events
                if event.event_type.endswith("_FAILED") and event.stage is not None
            ),
            3,
        )

        retry_count = sum(1 for event in events if event.event_type == "RETRY_QUEUED")
        failed_stage_count = sum(
            1
            for event in events
            if event.event_type.endswith("_FAILED") and event.stage is not None
        )

        queue_wait_ms = None
        if first_claimed_at is not None:
            queue_wait_ms = self._duration_ms(created_at, first_claimed_at)

        cycle_time_ms = self._duration_ms(created_at, effective_end)

        return {
            "job_id": job.id,
            "title": job.title,
            "status": job.status,
            "stage": job.stage,
            "created_at": created_at,
            "completed_at": terminal_at,
            "cycle_time_ms": cycle_time_ms,
            "queue_wait_ms": queue_wait_ms,
            "execution_time_ms": execution_time_ms,
            "retry_overhead_ms": retry_overhead_ms,
            "retry_count": retry_count,
            "failed_stage_count": failed_stage_count,
            "stage_metrics": stage_metrics,
        }

    def dashboard_summary(self) -> dict:
        with SessionLocal() as db:
            jobs = list(db.scalars(select(Job).order_by(Job.created_at.desc())))

        metrics = [self.job_metrics(job.id) for job in jobs]
        completed = [metric for metric in metrics if metric["status"] == "COMPLETED"]
        failed = [metric for metric in metrics if metric["status"] == "FAILED"]
        active = [metric for metric in metrics if metric["status"] not in TERMINAL_STATUSES]

        completed_cycle_times = [float(metric["cycle_time_ms"]) for metric in completed]
        queue_waits = [
            float(metric["queue_wait_ms"])
            for metric in metrics
            if metric["queue_wait_ms"] is not None
        ]

        total_execution_ms = round(
            sum(float(metric["execution_time_ms"]) for metric in metrics), 3
        )
        total_retry_overhead_ms = round(
            sum(float(metric["retry_overhead_ms"]) for metric in metrics), 3
        )

        return {
            "total_jobs": len(metrics),
            "completed_jobs": len(completed),
            "failed_jobs": len(failed),
            "active_jobs": len(active),
            "success_rate_percent": self._percent(len(completed), len(completed) + len(failed)),
            "average_cycle_time_ms": self._average(completed_cycle_times),
            "average_queue_wait_ms": self._average(queue_waits),
            "total_execution_time_ms": total_execution_ms,
            "total_retry_overhead_ms": total_retry_overhead_ms,
            "total_retries": sum(int(metric["retry_count"]) for metric in metrics),
            "total_failed_stages": sum(int(metric["failed_stage_count"]) for metric in metrics),
            "jobs": metrics,
        }

    @staticmethod
    def _event_time(events: list[WorkflowEvent], event_type: str) -> datetime | None:
        for event in events:
            if event.event_type == event_type:
                return event.created_at
        return None

    @staticmethod
    def _duration_ms(start: datetime, end: datetime) -> float:
        return round((end - start).total_seconds() * 1000, 3)

    @staticmethod
    def _average(values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    @staticmethod
    def _percent(numerator: int, denominator: int) -> float | None:
        if denominator == 0:
            return None
        return round((numerator / denominator) * 100, 2)


productivity_service = ProductivityService()
