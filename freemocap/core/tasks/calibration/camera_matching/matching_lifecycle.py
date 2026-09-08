"""Main-worker ownership of asynchronous matching attempts and stale results."""

from dataclasses import dataclass
from enum import StrEnum

from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingResult, CameraMatchingStatus


class MatchingLifecycleState(StrEnum):
    COLLECTING = "collecting"
    RUNNING = "running"
    MONITORING = "monitoring"
    SUSPENDED = "suspended"


@dataclass(frozen=True, slots=True)
class MatchingAttempt:
    generation: int
    sequence: int


class MatchingLifecycle:
    """An unsuccessful search suspends retries; absent evidence does not.

    The owning pipeline calls reset when calibration/source geometry changes or the
    user requests a retry. Background workers return their attempt with their result.
    Calls must occur on the owning worker; this object does not schedule background jobs.
    """

    def __init__(self) -> None:
        self.state = MatchingLifecycleState.COLLECTING
        self.result: CameraMatchingResult | None = None
        self._generation = 0
        self._sequence = 0
        self._active: MatchingAttempt | None = None

    def begin(self) -> MatchingAttempt:
        if self.state in (MatchingLifecycleState.RUNNING, MatchingLifecycleState.SUSPENDED):
            raise ValueError(f"Cannot begin matching while {self.state}")
        self._sequence += 1
        self._active = MatchingAttempt(generation=self._generation, sequence=self._sequence)
        self.state = MatchingLifecycleState.RUNNING
        return self._active

    def finish(self, *, attempt: MatchingAttempt, result: CameraMatchingResult) -> bool:
        if attempt.generation != self._generation:
            return False
        if attempt != self._active:
            raise ValueError("Matching result does not belong to the active attempt")
        self._active = None
        if result.status is CameraMatchingStatus.INSUFFICIENT:
            self.state = MatchingLifecycleState.COLLECTING
        else:
            self.result = result
            if result.status in (CameraMatchingStatus.INITIAL_ACCEPTED, CameraMatchingStatus.MATCHED, CameraMatchingStatus.DISABLED):
                self.state = MatchingLifecycleState.MONITORING
            else:
                self.state = MatchingLifecycleState.SUSPENDED
        return True

    def reset(self) -> None:
        self._generation += 1
        self._active = None
        self.result = None
        self.state = MatchingLifecycleState.COLLECTING
