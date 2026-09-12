import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.config import settings
from app.db import Job, SessionLocal


class HeartbeatService:
    def __init__(self, job_id: UUID, worker_id: str) -> None:
        self.job_id = job_id
        self.worker_id = worker_id
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._beat()
        self._thread = threading.Thread(
            target=self._run,
            name=f"heartbeat-{self.job_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=settings.worker_heartbeat_interval_seconds + 1)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.wait(settings.worker_heartbeat_interval_seconds):
            self._beat()

    def _beat(self) -> None:
        now = datetime.now(timezone.utc)
        lease_expires_at = now + timedelta(seconds=settings.worker_lease_seconds)
        with SessionLocal() as db:
            job = db.get(Job, self.job_id)
            if job is None or job.worker_id != self.worker_id:
                self._stop_event.set()
                return
            if job.status not in {"DISPATCHING", "RUNNING"}:
                return
            job.heartbeat_at = now
            job.lease_expires_at = lease_expires_at
            db.commit()
