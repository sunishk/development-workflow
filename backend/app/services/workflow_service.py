from uuid import UUID

from langgraph.graph.state import CompiledStateGraph

from app.db import Job, SessionLocal
from app.graph.factory_graph import WorkflowState, build_graph
from app.services.checkpointer import checkpointer_manager
from app.services.event_service import event_service


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

    def execute(self, job_id: UUID, worker_id: str) -> Job:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            if job.worker_id != worker_id:
                raise RuntimeError(f"Worker {worker_id} no longer owns job {job_id}")

            job.status = "RUNNING"
            job.error = None
            db.commit()
            db.refresh(job)

        config = {"configurable": {"thread_id": str(job_id)}}
        checkpoint = self.graph.get_state(config)
        has_checkpoint = bool(checkpoint.values)

        event_service.record(
            job_id,
            "WORKFLOW_RESUMED" if has_checkpoint else "WORKFLOW_STARTED",
            stage=checkpoint.values.get("stage") if has_checkpoint else "CREATED",
            worker_id=worker_id,
        )

        try:
            if has_checkpoint:
                result = self.graph.invoke(None, config)
            else:
                result = self.graph.invoke(self._initial_state(job_id), config)
        except Exception as exc:
            return self._mark_failed(job_id, worker_id, config, exc)

        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            if job.worker_id != worker_id:
                raise RuntimeError(f"Worker {worker_id} lost ownership of job {job_id}")

            job.status = result.get("status", "COMPLETED")
            job.stage = result.get("stage", "UNKNOWN")
            job.workspace_path = result.get("workspace_path") or job.workspace_path
            job.workspace_branch = result.get("workspace_branch") or job.workspace_branch
            job.error = None
            job.worker_id = None
            job.heartbeat_at = None
            job.lease_expires_at = None
            db.commit()
            db.refresh(job)

        event_service.record(job_id, "WORKFLOW_COMPLETED", stage=job.stage, worker_id=worker_id)
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
                "repository_url": job.repository_url,
                "base_branch": job.base_branch or "main",
                "workspace_path": job.workspace_path,
                "workspace_branch": job.workspace_branch,
                "repository_profile": None,
                "implementation_attempts": 0,
                "validation_feedback": None,
                "validation_passed": None,
            }

    def _mark_failed(self, job_id: UUID, worker_id: str, config: dict, exc: Exception) -> Job:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")

            job.status = "FAILED"
            job.error = str(exc)
            state = self.graph.get_state(config)
            if state.values:
                job.stage = state.values.get("stage", job.stage)
            job.worker_id = None
            job.heartbeat_at = None
            job.lease_expires_at = None
            db.commit()
            db.refresh(job)

        event_service.record(
            job_id,
            "WORKFLOW_FAILED",
            stage=job.stage,
            message=str(exc),
            worker_id=worker_id,
        )
        return job

    def get_job(self, job_id: UUID) -> Job | None:
        with SessionLocal() as db:
            return db.get(Job, job_id)


workflow_service = WorkflowService()
