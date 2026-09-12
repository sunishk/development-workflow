import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update

from app.core.config import settings
from app.db import Job, SessionLocal
from app.services.event_service import event_service


class WorkerManager:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._processes: dict[UUID, subprocess.Popen] = {}

    def start(self) -> None:
        self._stop_event.clear()
        self._recover_interrupted_jobs()
        self._thread = threading.Thread(
            target=self._dispatch_loop,
            name="workflow-dispatcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

        for process in self._processes.values():
            if process.poll() is None:
                process.terminate()

        for process in self._processes.values():
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        interrupted_job_ids = list(self._processes.keys())
        self._processes.clear()

        if interrupted_job_ids:
            with SessionLocal() as db:
                jobs = list(db.scalars(select(Job).where(Job.id.in_(interrupted_job_ids))))
                for job in jobs:
                    if job.status in {"DISPATCHING", "RUNNING"}:
                        job.status = "QUEUED"
                        job.error = "Interrupted by application shutdown"
                        job.worker_id = None
                        job.heartbeat_at = None
                        job.lease_expires_at = None
                db.commit()
            for job_id in interrupted_job_ids:
                event_service.record(job_id, "JOB_REQUEUED", message="Interrupted by application shutdown")

    def _recover_interrupted_jobs(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            jobs = list(
                db.scalars(
                    select(Job).where(
                        Job.status.in_(["DISPATCHING", "RUNNING"]),
                        (Job.lease_expires_at.is_(None)) | (Job.lease_expires_at < now),
                    )
                )
            )
            for job in jobs:
                job.status = "QUEUED"
                job.error = "Recovered after stale worker lease"
                job.worker_id = None
                job.heartbeat_at = None
                job.lease_expires_at = None
            db.commit()

        for job in jobs:
            event_service.record(job.id, "LEASE_EXPIRED", stage=job.stage, message="Stale worker lease recovered")
            event_service.record(job.id, "JOB_REQUEUED", stage=job.stage, message="Recovered after stale worker lease")

    def _dispatch_loop(self) -> None:
        while not self._stop_event.is_set():
            self._reap_finished_processes()
            self._recover_interrupted_jobs()

            while len(self._processes) < settings.max_workers:
                claimed = self._claim_next_job()
                if claimed is None:
                    break
                job_id, worker_id = claimed
                self._spawn_worker(job_id, worker_id)

            self._stop_event.wait(settings.worker_poll_interval_seconds)

    def _claim_next_job(self) -> tuple[UUID, str] | None:
        now = datetime.now(timezone.utc)
        lease_expires_at = now + timedelta(seconds=settings.worker_lease_seconds)
        worker_id = str(uuid4())

        with SessionLocal() as db:
            stmt = (
                select(Job)
                .where(Job.status == "QUEUED")
                .order_by(Job.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            job = db.scalar(stmt)
            if job is None:
                return None

            job.status = "DISPATCHING"
            job.error = None
            job.worker_id = worker_id
            job.heartbeat_at = now
            job.lease_expires_at = lease_expires_at
            db.commit()
            job_id = job.id

        event_service.record(job_id, "JOB_CLAIMED", worker_id=worker_id)
        return job_id, worker_id

    def _spawn_worker(self, job_id: UUID, worker_id: str) -> None:
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "app.worker", str(job_id), worker_id],
                cwd=settings.worker_cwd,
            )
        except Exception as exc:
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if job is not None:
                    job.status = "FAILED"
                    job.error = f"Unable to start worker: {exc}"
                    job.worker_id = None
                    job.heartbeat_at = None
                    job.lease_expires_at = None
                    db.commit()
            event_service.record(job_id, "WORKER_START_FAILED", message=str(exc), worker_id=worker_id)
            return

        self._processes[job_id] = process
        event_service.record(job_id, "WORKER_PROCESS_STARTED", worker_id=worker_id)

    def _reap_finished_processes(self) -> None:
        finished = [
            job_id
            for job_id, process in self._processes.items()
            if process.poll() is not None
        ]

        for job_id in finished:
            process = self._processes.pop(job_id)
            if process.returncode == 0:
                continue

            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if job is not None and job.status in {"DISPATCHING", "RUNNING"}:
                    job.status = "FAILED"
                    job.error = f"Worker exited with code {process.returncode}"
                    job.worker_id = None
                    job.heartbeat_at = None
                    job.lease_expires_at = None
                    db.commit()
            event_service.record(job_id, "WORKER_EXITED", message=f"Exit code {process.returncode}")


worker_manager = WorkerManager()
