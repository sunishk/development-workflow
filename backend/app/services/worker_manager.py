import subprocess
import sys
import threading
import time
from uuid import UUID

from sqlalchemy import select, update

from app.core.config import settings
from app.db import Job, SessionLocal


class WorkerManager:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._processes: dict[UUID, subprocess.Popen] = {}

    def start(self) -> None:
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

    def _recover_interrupted_jobs(self) -> None:
        with SessionLocal() as db:
            db.execute(
                update(Job)
                .where(Job.status.in_(["DISPATCHING", "RUNNING"]))
                .values(status="QUEUED", error="Recovered after application restart")
            )
            db.commit()

    def _dispatch_loop(self) -> None:
        while not self._stop_event.is_set():
            self._reap_finished_processes()

            while len(self._processes) < settings.max_workers:
                job_id = self._claim_next_job()
                if job_id is None:
                    break
                self._spawn_worker(job_id)

            self._stop_event.wait(settings.worker_poll_interval_seconds)

    def _claim_next_job(self) -> UUID | None:
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
            db.commit()
            return job.id

    def _spawn_worker(self, job_id: UUID) -> None:
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "app.worker", str(job_id)],
                cwd=settings.worker_cwd,
            )
        except Exception as exc:
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if job is not None:
                    job.status = "FAILED"
                    job.error = f"Unable to start worker: {exc}"
                    db.commit()
            return

        self._processes[job_id] = process

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
                    db.commit()


worker_manager = WorkerManager()
