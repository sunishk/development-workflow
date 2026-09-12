from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db import SessionLocal, TestFailureControl
from app.graph.test_hooks import failure_controller

router = APIRouter(prefix="/test", tags=["test controls"])


class FailureRequest(BaseModel):
    stage: str = Field(pattern="^(INTAKE|REQUIREMENTS|TECH_SPEC|TASKS)$")
    failures: int = Field(default=1, ge=1, le=10)


@router.post("/failure")
def configure_failure(request: FailureRequest) -> dict[str, str | int]:
    failure_controller.fail_stage = None
    failure_controller.failures_remaining = 0

    with SessionLocal() as db:
        control = db.get(TestFailureControl, 1)
        if control is None:
            control = TestFailureControl(id=1)
            db.add(control)
        control.stage = request.stage
        control.failures_remaining = request.failures
        db.commit()

    return {
        "stage": request.stage,
        "failures_remaining": request.failures,
    }


@router.delete("/failure")
def clear_failure() -> dict[str, str]:
    failure_controller.fail_stage = None
    failure_controller.failures_remaining = 0

    with SessionLocal() as db:
        control = db.get(TestFailureControl, 1)
        if control is not None:
            control.stage = None
            control.failures_remaining = 0
            db.commit()

    return {"status": "cleared"}
