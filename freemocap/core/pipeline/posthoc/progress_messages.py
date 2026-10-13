from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from skellycam.core.types.type_overloads import CameraIdString


class RunTimingSnapshot(BaseModel):
    """Server-measured duration; one motion frame spans all recorded cameras."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    elapsed_seconds: float = Field(ge=0)
    motion_frame_count: int | None = Field(default=None, ge=0)
    seconds_per_motion_frame: float | None = Field(default=None, ge=0)


class OperationProgressSnapshot(BaseModel):
    """One independently executing operation, described by its producer."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    operation_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    status: Literal["waiting", "running", "complete", "failed", "cancelled"]
    progress_fraction: float | None = Field(default=None, ge=0, le=1)
    detail: str = ""
    completed: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    unit: str | None = None
    elapsed_seconds: float | None = Field(default=None, ge=0)
    seconds_per_motion_frame: float | None = Field(default=None, ge=0)


@dataclass
class PipelineProgressMessage:
    pipeline_id: str = ""
    pipeline_type: str = ""
    phase: str = ""
    progress_fraction: float = 0.0
    detail: str = ""
    recording_name: str = ""
    recording_path: str = ""
    # None means this producer has no operation update, not "erase prior work".
    operations: tuple[OperationProgressSnapshot, ...] | None = None
    timing: RunTimingSnapshot | None = None


@dataclass
class VideoNodeProgressMessage(PipelineProgressMessage):
    camera_id: CameraIdString = ""


@dataclass
class AggregatorNodeProgressMessage(PipelineProgressMessage):
    pass


@dataclass
class SyncJobProgressMessage(PipelineProgressMessage):
    message_type: str = "sync_progress"
