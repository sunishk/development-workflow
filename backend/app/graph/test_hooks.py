from dataclasses import dataclass

from sqlalchemy import select

from app.db import SessionLocal, TestFailureControl


@dataclass
class FailureController:
    """Controls deterministic failures used by tests and local retry demos."""

    fail_stage: str | None = None
    failures_remaining: int = 0

    def should_fail(self, stage: str) -> bool:
        if self.fail_stage == stage and self.failures_remaining > 0:
            self.failures_remaining -= 1
            return True

        with SessionLocal() as db:
            stmt = (
                select(TestFailureControl)
                .where(TestFailureControl.id == 1)
                .with_for_update()
            )
            control = db.scalar(stmt)
            if (
                control is None
                or control.stage != stage
                or control.failures_remaining <= 0
            ):
                return False

            control.failures_remaining -= 1
            db.commit()
            return True


failure_controller = FailureController()
