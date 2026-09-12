from dataclasses import dataclass


@dataclass
class FailureController:
    """Controls deterministic failures used by tests and local retry demos."""

    fail_stage: str | None = None
    failures_remaining: int = 0

    def should_fail(self, stage: str) -> bool:
        if self.fail_stage != stage or self.failures_remaining <= 0:
            return False
        self.failures_remaining -= 1
        return True


failure_controller = FailureController()
