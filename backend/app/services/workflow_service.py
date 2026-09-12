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

    def create_and_run(self, job_id: UUID) -> Job:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            job.status = "RUNNING"
            job.stage = "INTAKE"
            job.error = None
            db.commit()
            db.refresh(job)

            initial_state: WorkflowState = {
                "job_id": str(job.id),
                "title": job.title,
                "description": job.description,
                "stage": job.stage,
                "status": job.status,
                "requirements": "",
                "tech_spec": "",
                "tasks": [],
            }

        config = {"configurable": {"thread_id": str(job_id)}}

        try:
            result = self.graph.invoke(initial_state, config)
        except Exception as exc:
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if job:
                    job.status = "FAILED"
                    job.error = str(exc)
                    state = self.graph.get_state(config)
                    if state.values:
                        job.stage = state.values.get("stage", job.stage)
                    db.commit()
                    db.refresh(job)
                    return job
            raise

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

    def retry(self, job_id: UUID) -> Job:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            job.status = "RUNNING"
            job.error = None
            db.commit()

        config = {"configurable": {"thread_id": str(job_id)}}

        try:
            result = self.graph.invoke(None, config)
        except Exception as exc:
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if job:
                    job.status = "FAILED"
                    job.error = str(exc)
                    state = self.graph.get_state(config)
                    if state.values:
                        job.stage = state.values.get("stage", job.stage)
                    db.commit()
                    db.refresh(job)
                    return job
            raise

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

    def get_job(self, job_id: UUID) -> Job | None:
        with SessionLocal() as db:
            return db.get(Job, job_id)


workflow_service = WorkflowService()
