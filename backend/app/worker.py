import sys
from uuid import UUID

from app.services.checkpointer import checkpointer_manager
from app.services.workflow_service import workflow_service


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m app.worker <job-id>")
        return 2

    job_id = UUID(sys.argv[1])
    workflow_service.start()
    try:
        workflow_service.execute(job_id)
        return 0
    finally:
        workflow_service.stop()
        checkpointer_manager.stop()


if __name__ == "__main__":
    raise SystemExit(main())
