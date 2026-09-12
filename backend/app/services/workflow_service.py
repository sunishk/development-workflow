from uuid import UUID

from langgraph.graph import CompiledStateGraph

from app.db import Job, SessionLocal
from app.graph.factory_graph import WorkflowState, build_graph
from app.services.checkpointer import checkpointer_manager


class WorkflowService:
    def __init__(self) -> None:
        self._graph: CompiledStateGraph | None = None

    def start(self) -> None:
        self._graph = build_graph(checkpointer_manager.start())

    def stop(self) -> None:
        self._graph = None

    @property
    def graph(self) -> CompiledStateGraph:
        if self._graph is None:
            raise RuntimeError("Workflow service has not been started")
        return self._graph

    def execute(self, job_id: UUID) -> Job:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            job.status = "RUNNING"
            job.error = None
            db.commit()
            db.refresh(job)

        config = {"configurable": {"thread_id": str(job_id)}}
        checkpoint = self.graph.get_state(config)
        has_checkpoint = bool(checkpoint.values)

        try:
            if has_checkpoint:
                result = self.graph.invoke(None, config)
            else:
                result = self.graph.invoke(self._initial_state(job_id), config)
        except Exception as exc:
            return self._mark_failed(job_id, config, exc)

        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            job.status = result.get("status", "COMPLETED")
            job.stage = result.get("stage", "UNKNOWN")
            job.error = None
            db.commit()
            db.refresh(job)
            return job

    def _initial_state(self, job_id: UUID) -> WorkflowState:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            return {
                "job_id": str(job.id),
                "title": job.title,
                "description": job.description,
                "stage": "CREATED",
                "status": "PENDING",
                "requirements": "",
                "tech_spec": "",
                "tasks": [],
            }

    def _mark_failed(self, job_id: UUID, config: dict, exc: Exception) -> Job:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")

            job.status = "FAILED"
            job.error = str(exc)
            state = self.graph.get_state(config)
            if state.values:
                job.stage = state.values.get("stage", job.stage)
            db.commit()
            db.refresh(job)
            return job

    def get_job(self, job_id: UUID) -> Job | None:
        with SessionLocal() as db:
            return db.get(Job, job_id)


workflow_service = WorkflowService()
