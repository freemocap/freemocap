"""Frame-local camera readiness, separate from successful stream completion.

Single-owner state for one execution/group. Payload storage, scheduling, retries
and transport are deliberately outside this contract. Ready keys contain no images.
"""
from dataclasses import dataclass
from enum import StrEnum


class ProducerOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class CameraFrameKey:
    execution: str
    sensor_group: str
    camera: str
    frame: int

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip()
               for value in (self.execution, self.sensor_group, self.camera)):
            raise ValueError("Frame keys require nonempty string identities")
        if type(self.frame) is not int or self.frame < 0:
            raise ValueError("Frame ordinal must be a nonnegative integer")


class CameraFrameJoin:
    def __init__(self, *, execution: str, sensor_group: str,
                 cameras: tuple[str, ...], frames: range) -> None:
        if not execution or not sensor_group or not cameras or any(not camera for camera in cameras):
            raise ValueError("Execution, group and camera identities are required")
        if len(set(cameras)) != len(cameras):
            raise ValueError("Camera identities must be unique")
        if not frames or frames.start < 0 or frames.step != 1:
            raise ValueError("Coverage must be a nonempty consecutive nonnegative frame range")
        self.execution = execution
        self.sensor_group = sensor_group
        self.cameras = cameras
        self.frames = frames
        self._seen = {camera: set() for camera in cameras}
        self._outcomes: dict[str, ProducerOutcome] = {}

    def receive(self, key: CameraFrameKey) -> tuple[CameraFrameKey, ...] | None:
        """Return camera-ordered keys exactly when this frame becomes ready.

        A valid empty detection is delivered exactly like any other observation.
        Caller must validate/store the payload before announcing its key here.
        """
        if (key.execution, key.sensor_group) != (self.execution, self.sensor_group):
            raise ValueError("Foreign execution or sensor group")
        if key.camera not in self._seen or key.frame not in self.frames:
            raise ValueError("Undeclared camera or frame")
        if key.camera in self._outcomes:
            raise ValueError("Data received after terminal producer outcome")
        if key.frame in self._seen[key.camera]:
            raise ValueError("Duplicate camera/frame result")
        self._seen[key.camera].add(key.frame)
        if all(key.frame in self._seen[camera] for camera in self.cameras):
            return tuple(CameraFrameKey(self.execution, self.sensor_group, camera, key.frame)
                         for camera in self.cameras)
        return None

    def finish(self, camera: str, outcome: ProducerOutcome, *, execution: str, sensor_group: str) -> None:
        if (execution, sensor_group) != (self.execution, self.sensor_group):
            raise ValueError("Foreign execution or sensor group")
        if camera not in self._seen or camera in self._outcomes:
            raise ValueError("Unknown or already terminal camera")
        if not isinstance(outcome, ProducerOutcome):
            raise ValueError("Expected an explicit producer outcome")
        if outcome == ProducerOutcome.SUCCEEDED and len(self._seen[camera]) != len(self.frames):
            raise ValueError("Successful completion requires exact declared frame coverage")
        self._outcomes[camera] = outcome

    @property
    def complete(self) -> bool:
        return all(self._outcomes.get(camera) == ProducerOutcome.SUCCEEDED for camera in self.cameras)

    @property
    def failed(self) -> bool:
        return ProducerOutcome.FAILED in self._outcomes.values()
