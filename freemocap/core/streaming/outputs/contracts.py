"""Output control and emitter boundary, separate from scientific stream contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from freemocap.core.streaming.message_model import FrameMessage


@dataclass(frozen=True, slots=True)
class OutputSample:
    """Owned channel bytes plus immutable acquisition-clock provenance.

    source_timestamp_ns is the source multi-camera measurement instant, NOT when
    this object was composed or sent. Individual camera midpoints retain integer
    nanoseconds even when the multi-camera mean has a fractional representation.
    """

    frame: FrameMessage
    pipeline_id: str
    source_timestamp_ns: int | float
    camera_timestamps_ns: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class SourceBatch:
    samples: tuple[OutputSample, ...] = ()
    active_sources: tuple[str, ...] = ()
    errors: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class OutputSource(Protocol):
    def source_ids(self) -> tuple[str, ...]: ...
    def poll(self) -> SourceBatch: ...


@dataclass(frozen=True, slots=True)
class OutputEmission:
    sent: bool
    readiness: Literal['waiting_for_receiver', 'sending']
    outlets_advertised: int
    outlets_connected: int


@runtime_checkable
class OutputEmitter(Protocol):
    def emit(self, sample: OutputSample) -> OutputEmission | None: ...
    def close(self) -> None: ...


class StartOutputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol: str = Field(min_length=1)
    # None selects the sole active pipeline; multiple pipelines require a choice.
    # An explicit ID may be configured while idle, before that source is available.
    pipeline_id: str | None = Field(default=None, min_length=1)
    config: dict = Field(default_factory=dict)
    queue_capacity: int = Field(default=8, ge=1, le=256)


class OutputState(BaseModel):
    id: str
    protocol: str
    pipeline_id: str | None
    active_pipeline_id: str | None = None
    status: Literal["idle", "running", "failed", "stopped"] = "idle"
    config: dict
    queue_capacity: int
    overflow_policy: Literal["latest", "fail"]
    readiness: Literal['preparing', 'waiting_for_receiver', 'sending'] | None = None
    frames_before_ready: int = 0
    frames_without_receivers: int = 0
    outlets_advertised: int = 0
    outlets_connected: int = 0
    frames_emitted: int = 0
    source_frame_gaps: int = 0
    queue_dropped_frames: int = 0
    queue_overflows: int = 0
    last_frame_number: int | None = None
    # Decimal text avoids JSON/JS integer precision loss. Units are in the name.
    last_capture_timestamp_ns: str | None = None
    error: str | None = None


class OutputCapability(BaseModel):
    protocol: str
    config_schema: dict
    overflow_policy: Literal["latest", "fail"]
    available: bool
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class ProtocolDefinition:
    name: str
    config_type: type[BaseModel]
    create: Callable[[BaseModel], OutputEmitter]
    overflow_policy: Literal["latest", "fail"]
    unavailable_reason: Callable[[], str | None] = lambda: None


class OutputConflictError(ValueError):
    """The selected source or output capacity needs an explicit user choice."""


class OutputUnavailableError(RuntimeError):
    """A required protocol runtime is unavailable; no output was started."""
