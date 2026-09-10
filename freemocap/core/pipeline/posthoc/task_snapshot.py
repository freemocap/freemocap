"""Complete task state, retained independently of its delivery connections."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from freemocap.core.pipeline.posthoc.progress_messages import (
    PipelineProgressMessage,
    VideoNodeProgressMessage,
)
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.core.recording.recording_access import RecordingOwner


class SnapshotModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class TaskProgress(SnapshotModel):
    phase: str = Field(min_length=1)
    progress_fraction: float | None = Field(ge=0, le=1)
    detail: str

    @classmethod
    def from_message(cls, *, message: PipelineProgressMessage) -> "TaskProgress":
        measured = message.phase in (
            "processing_images",
            "collecting_camera_output",
            "complete",
        )
        return cls(
            phase=str(message.phase),
            progress_fraction=message.progress_fraction if measured else None,
            detail=message.detail,
        )


class CameraTaskSnapshot(SnapshotModel):
    node_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    progress: TaskProgress


class TaskSnapshot(SnapshotModel):
    task_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    task_type: Literal["calibration", "mocap"]
    recording: RecordingStructure
    status: Literal["running", "complete", "failed", "cancelled"]
    progress: TaskProgress
    cameras: tuple[CameraTaskSnapshot, ...]
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_cameras(self) -> "TaskSnapshot":
        if len({camera.node_id for camera in self.cameras}) != len(self.cameras):
            raise ValueError("Camera task node IDs must be unique")
        return self


class TaskRegistrySnapshot(SnapshotModel):
    server_instance_id: UUID
    revision: int = Field(ge=0)
    tasks: tuple[TaskSnapshot, ...]
    recording_owners: tuple[RecordingOwner, ...]


@dataclass
class TaskRegistry:
    server_instance_id: UUID = field(default_factory=uuid4)
    revision: int = 0
    tasks: dict[str, TaskSnapshot] = field(default_factory=dict)
    completed_task_limit: int = 100

    def prune_completed(self, *, active_task_ids: set[str]) -> None:
        completed = sorted(
            (
                task
                for task in self.tasks.values()
                if task.status != "running" and task.task_id not in active_task_ids
            ),
            key=lambda task: task.updated_at,
        )
        for task in completed[: -self.completed_task_limit]:
            del self.tasks[task.task_id]
            self.revision += 1

    def register(
        self,
        *,
        task_id: str,
        task_type: Literal["calibration", "mocap"],
        recording: RecordingStructure,
    ) -> None:
        if task_id in self.tasks:
            raise ValueError(f"Task already registered: {task_id}")
        now = datetime.now(tz=timezone.utc)
        self.tasks[task_id] = TaskSnapshot(
            task_id=task_id,
            revision=1,
            task_type=task_type,
            recording=recording.model_copy(deep=True),
            status="running",
            progress=TaskProgress(
                phase="setting_up", progress_fraction=None, detail="Preparing task"
            ),
            cameras=(),
            created_at=now,
            updated_at=now,
        )
        self.revision += 1

    def update(self, *, task_id: str, messages: list[PipelineProgressMessage]) -> None:
        previous = self.tasks[task_id]
        progress = previous.progress
        cameras = {camera.node_id: camera for camera in previous.cameras}
        for message in messages:
            if message.pipeline_id == task_id:
                progress = TaskProgress.from_message(message=message)
            elif isinstance(message, VideoNodeProgressMessage):
                cameras[message.pipeline_id] = CameraTaskSnapshot(
                    node_id=message.pipeline_id,
                    camera_id=message.camera_id,
                    progress=TaskProgress.from_message(message=message),
                )
            else:
                raise ValueError(
                    f"Unidentified task progress node: {message.pipeline_id}"
                )
        status = (
            "complete"
            if progress.phase == "complete"
            else "failed"
            if progress.phase == "failed"
            else "running"
        )
        ordered = tuple(sorted(cameras.values(), key=lambda camera: camera.node_id))
        if (progress, ordered, status) == (
            previous.progress,
            previous.cameras,
            previous.status,
        ):
            return
        self.tasks[task_id] = previous.model_copy(
            update={
                "progress": progress,
                "cameras": ordered,
                "status": status,
                "revision": previous.revision + 1,
                "updated_at": datetime.now(tz=timezone.utc),
            }
        )
        self.revision += 1

    def cancel(self, *, task_id: str) -> None:
        previous = self.tasks[task_id]
        if previous.status != "running":
            return
        self.tasks[task_id] = previous.model_copy(
            update={
                "status": "cancelled",
                "progress": TaskProgress(
                    phase="failed", progress_fraction=None, detail="Stopped by user"
                ),
                "revision": previous.revision + 1,
                "updated_at": datetime.now(tz=timezone.utc),
            }
        )
        self.revision += 1

    def snapshot(self) -> TaskRegistrySnapshot:
        return TaskRegistrySnapshot(
            recording_owners=(),
            server_instance_id=self.server_instance_id,
            revision=self.revision,
            tasks=tuple(self.tasks.values()),
        ).model_copy(deep=True)
