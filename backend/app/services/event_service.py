from uuid import UUID

from sqlalchemy import select

from app.db import SessionLocal, WorkflowEvent


class EventService:
    def record(
        self,
        job_id: UUID,
        event_type: str,
        *,
        stage: str | None = None,
        message: str | None = None,
        worker_id: str | None = None,
    ) -> None:
        with SessionLocal() as db:
            db.add(
                WorkflowEvent(
                    job_id=job_id,
                    event_type=event_type,
                    stage=stage,
                    message=message,
                    worker_id=worker_id,
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


event_service = EventService()
