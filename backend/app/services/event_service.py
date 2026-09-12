from collections import defaultdict
from uuid import UUID

from sqlalchemy import select

from app.db import Job, SessionLocal, WorkflowEvent


class EventService:
    def record(
        self,
        job_id: UUID,
        event_type: str,
        *,
        stage: str | None = None,
        message: str | None = None,
        worker_id: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        with SessionLocal() as db:
            if worker_id is None:
                job = db.get(Job, job_id)
                worker_id = job.worker_id if job is not None else None

            db.add(
                WorkflowEvent(
                    job_id=job_id,
                    event_type=event_type,
                    stage=stage,
                    message=message,
                    worker_id=worker_id,
                    duration_ms=duration_ms,
                )
            )
            db.commit()

    def list_for_job(self, job_id: UUID) -> list[WorkflowEvent]:
        with SessionLocal() as db:
            return list(
                db.scalars(
                    select(WorkflowEvent)
                    .where(WorkflowEvent.job_id == job_id)
                    .order_by(WorkflowEvent.created_at, WorkflowEvent.id)
                )
            )

    def stage_metrics(self, job_id: UUID) -> list[dict[str, int | float | str | None]]:
        metrics: dict[str, dict[str, int | float | str | None]] = defaultdict(
            lambda: {
                "stage": None,
                "attempts": 0,
                "completed_attempts": 0,
                "failed_attempts": 0,
                "total_duration_ms": 0.0,
                "last_duration_ms": None,
            }
        )

        for event in self.list_for_job(job_id):
            if event.stage is None:
                continue

            stage_metrics = metrics[event.stage]
            stage_metrics["stage"] = event.stage

            if event.event_type == f"{event.stage}_STARTED":
                stage_metrics["attempts"] = int(stage_metrics["attempts"]) + 1
            elif event.event_type == f"{event.stage}_COMPLETED":
                stage_metrics["completed_attempts"] = int(stage_metrics["completed_attempts"]) + 1
                self._add_duration(stage_metrics, event.duration_ms)
            elif event.event_type == f"{event.stage}_FAILED":
                stage_metrics["failed_attempts"] = int(stage_metrics["failed_attempts"]) + 1
                self._add_duration(stage_metrics, event.duration_ms)

        return [metrics[stage] for stage in sorted(metrics)]

    @staticmethod
    def _add_duration(
        stage_metrics: dict[str, int | float | str | None], duration_ms: float | None
    ) -> None:
        if duration_ms is None:
            return
        stage_metrics["total_duration_ms"] = round(
            float(stage_metrics["total_duration_ms"]) + duration_ms, 3
        )
        stage_metrics["last_duration_ms"] = round(duration_ms, 3)


event_service = EventService()
