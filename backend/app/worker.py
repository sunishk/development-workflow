import sys
from uuid import UUID

from app.services.checkpointer import checkpointer_manager
from app.services.heartbeat_service import HeartbeatService
from app.services.workflow_service import workflow_service


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python -m app.worker <job-id> <worker-id>")
        return 2

    job_id = UUID(sys.argv[1])
    worker_id = sys.argv[2]
    heartbeat = HeartbeatService(job_id, worker_id)

    workflow_service.start()
    heartbeat.start()
    try:
        workflow_service.execute(job_id, worker_id)
        return 0
    finally:
        heartbeat.stop()
        workflow_service.stop()
        checkpointer_manager.stop()


if __name__ == "__main__":
    raise SystemExit(main())
