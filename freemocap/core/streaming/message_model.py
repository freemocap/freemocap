"""The self-describing message model (frozen slots dataclasses + CBOR codec).

Every message is a frozen slots dataclass: a ClassVar "kind" (a MessageKind
StrEnum), the envelope fields (version, timestamp, sequence), and a kind payload.
Each message is self-describing — it carries everything needed to decode it.
Serialization is encode_message, which walks the dataclass fields
in declaration order (the documented field order: kind, version, timestamp,
sequence, then the payload) and omits None-valued optional fields.

This module is a pure leaf (stdlib + cbor2 only) so the golden-fixture generator
and the backend can import it without the freemocap eager-logging init. Factory
classmethods that need skellyforge (ModelMessage.from_standard_human) import
lazily inside the method.

See current-work-plans/03-transport/message-protocol.md.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum, StrEnum
from typing import Any, ClassVar

import cbor2

CURRENT_VERSION: int = 0


class MessageKind(StrEnum):
    """The message kind (the envelope discriminator), split by source."""

    FRAME = "frame"
    CONVENTION = "convention"
    MODEL = "model"
    CAMERA_LAYOUT = "camera_layout"
    LOG = "log"
    FRAMERATE = "framerate"
    APP_STATE = "app_state"
    PROGRESS = "progress"


class ChannelKind(StrEnum):
    """The frame channel kind (a named column block)."""

    KEYPOINTS_3D = "KEYPOINTS_3D"
    LANDMARKS_3D = "LANDMARKS_3D"
    SEGMENT_ORIGINS = "SEGMENT_ORIGINS"
    ROTATIONS_LOCAL = "ROTATIONS_LOCAL"
    ROTATIONS_WORLD = "ROTATIONS_WORLD"
    DERIVED_POINTS = "DERIVED_POINTS"
    OVERLAY_2D = "OVERLAY_2D"
    SEGMENT_LENGTHS = "SEGMENT_LENGTHS"
    IMAGE_JPEG = "IMAGE_JPEG"  # producer tag; the frame routes it to the image field, not a channel
    OVERLAY_REPROJECTIONS = "OVERLAY_REPROJECTIONS"


class Units(StrEnum):
    MILLIMETERS = "mm"
    CENTIMETERS = "cm"
    METERS = "m"


class Handedness(StrEnum):
    RIGHT = "right"
    LEFT = "left"


class Axis(StrEnum):
    PLUS_X = "+x"
    MINUS_X = "-x"
    PLUS_Y = "+y"
    MINUS_Y = "-y"
    PLUS_Z = "+z"
    MINUS_Z = "-z"


class RotationFrame(StrEnum):
    LOCAL = "local"
    WORLD = "world"


class RotationForm(StrEnum):
    QUATERNION = "quaternion"
    EULER = "euler"


# ── Frame payload dataclasses ───────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ChannelBlock:
    """One named column block: kind + names + columns + data (a byte string of
    packed float32 little-endian, columns by names, row-major). camera_id is
    present only on the per-camera overlay channels (OVERLAY_2D /
    OVERLAY_REPROJECTIONS)."""

    kind: ChannelKind
    names: tuple[str, ...]
    columns: tuple[str, ...]
    data: bytes
    camera_id: str | None = None

    @classmethod
    def from_float32_rows(
        cls,
        *,
        kind: ChannelKind,
        names: tuple[str, ...],
        columns: tuple[str, ...],
        rows: list[list[float]],
        camera_id: str | None = None,
    ) -> ChannelBlock:
        """Pack row-major float32 little-endian rows into a ChannelBlock."""
        packed = bytearray()
        for row in rows:
            packed += struct.pack(f"<{len(row)}f", *row)
        return cls(
            kind=kind,
            names=tuple(names),
            columns=tuple(columns),
            data=bytes(packed),
            camera_id=camera_id,
        )


@dataclass(frozen=True, slots=True)
class Subject:
    """One subject's channels inside a frame (multi-person headroom)."""

    subject_id: int
    channels: tuple[ChannelBlock, ...]


# ── Envelope base ───────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class MessageEnvelope:
    """The shared envelope fields (version, timestamp, sequence). Each concrete
    message subclass declares its own ClassVar kind."""

    version: int = CURRENT_VERSION
    timestamp: float = 0.0
    sequence: int = 0


# ── Replace kinds (low-frequency, idempotent, latest-wins) ──────────────

@dataclass(frozen=True, slots=True)
class ConventionMessage(MessageEnvelope):
    kind: ClassVar[MessageKind] = MessageKind.CONVENTION
    units: Units = Units.MILLIMETERS
    handedness: Handedness = Handedness.RIGHT
    up_axis: Axis = Axis.PLUS_Z
    forward_axis: Axis = Axis.PLUS_X
    rotation_frame: RotationFrame = RotationFrame.LOCAL
    rotation_form: RotationForm = RotationForm.QUATERNION


@dataclass(frozen=True, slots=True)
class ModelMessage(MessageEnvelope):
    kind: ClassVar[MessageKind] = MessageKind.MODEL
    segments: tuple[str, ...] = ()
    orientations: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    axes: dict[str, str] = field(default_factory=dict)
    lengths: dict[str, float] = field(default_factory=dict)
    connections: tuple[tuple[str, str], ...] = ()
    hierarchy: dict[str, tuple[str, ...]] = field(default_factory=dict)
    parents: dict[str, str | None] = field(default_factory=dict)
    rest_positions: dict[str, tuple[float, float, float]] = field(default_factory=dict)

    @classmethod
    def from_standard_human(cls, standard_human: Any) -> ModelMessage:
        """Build from skellyforge's StandardHuman (rest basis -> orientations,
        exact-axis names -> axes, length_ratio x nominal height -> lengths)."""
        from freemocap.core.streaming.constants import NOMINAL_SUBJECT_HEIGHT_MM  # noqa: PLC0415
        from skellyforge.kinematics.quaternion_math import RotationQuaternion  # noqa: PLC0415
        from skellyforge.skellymodels.standard_human.reference_geometry import build_reference_geometry  # noqa: PLC0415

        lengths = {
            segment.name: segment.length_ratio * NOMINAL_SUBJECT_HEIGHT_MM
            for segment in standard_human.segments
        }
        geometry = build_reference_geometry(list(standard_human.segments), lengths)

        orientations: dict[str, tuple[float, float, float, float]] = {}
        for segment in standard_human.segments:
            quaternion = RotationQuaternion.from_rotation_matrix(
                geometry.segments[segment.name].basis.T
            )
            orientations[segment.name] = (
                float(quaternion.w),
                float(quaternion.x),
                float(quaternion.y),
                float(quaternion.z),
            )

        rest_positions = {
            name: (float(pos[0]), float(pos[1]), float(pos[2]))
            for name, pos in geometry.landmarks.items()
        }
        axes = {segment.name: segment.exact_axis.axis for segment in standard_human.segments}
        connections = tuple(
            (segment.name, child.name)
            for segment in standard_human.segments
            for child in standard_human.get_children(segment.name)
        )
        hierarchy = {key: tuple(value) for key, value in standard_human.joint_hierarchy.items()}
        parents = dict(standard_human.segment_parents)

        return cls(
            segments=tuple(standard_human.segment_names),
            orientations=orientations,
            axes=axes,
            lengths=lengths,
            connections=connections,
            hierarchy=hierarchy,
            parents=parents,
            rest_positions=rest_positions,
        )


@dataclass(frozen=True, slots=True)
class CameraLayoutMessage(MessageEnvelope):
    kind: ClassVar[MessageKind] = MessageKind.CAMERA_LAYOUT
    camera_ids: tuple[str, ...] = ()
    image_sizes: dict[str, tuple[int, int]] = field(default_factory=dict)


# ── Frame kind ──────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class FrameMessage(MessageEnvelope):
    kind: ClassVar[MessageKind] = MessageKind.FRAME
    frame_number: int = 0
    subjects: tuple[Subject, ...] = ()
    image: bytes | None = None  # optional — the opaque multi-camera JPEG blob


# ── Append / telemetry kinds ────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LogRecord:
    """The skellylogs logging record (mirrors the TS LogRecordSchema)."""

    name: str = ""
    msg: str | None = ""
    args: tuple[Any, ...] = ()
    levelname: str = ""
    levelno: int = 0
    pathname: str = ""
    filename: str = ""
    module: str = ""
    exc_info: str | None = None
    exc_text: str | None = None
    stack_info: str | None = None
    lineno: int = 0
    funcName: str = ""
    created: float = 0.0
    msecs: float = 0.0
    relativeCreated: float = 0.0
    thread: int = 0
    threadName: str = ""
    processName: str = ""
    process: int = 0
    delta_t: str = ""
    message: str = ""
    asctime: str = ""
    formatted_message: str = ""
    type: str = ""
    source: str = "server"

    @classmethod
    def from_logging_dict(cls, record: dict[str, Any]) -> LogRecord:
        """Build from a skellylogs logging-record dict (unknown keys ignored)."""
        known = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in record.items() if key in known})


@dataclass(frozen=True, slots=True)
class LogMessage(MessageEnvelope):
    kind: ClassVar[MessageKind] = MessageKind.LOG
    record: LogRecord = field(default_factory=LogRecord)


@dataclass(frozen=True, slots=True)
class DetailedFramerate:
    mean_frame_duration_ms: float = 0.0
    mean_frames_per_second: float = 0.0
    frame_duration_max: float = 0.0
    frame_duration_min: float = 0.0
    frame_duration_mean: float = 0.0
    frame_duration_stddev: float = 0.0
    frame_duration_median: float = 0.0
    frame_duration_coefficient_of_variation: float = 0.0
    calculation_window_size: int = 0
    framerate_source: str = ""

    @classmethod
    def from_current_framerate(cls, framerate: Any) -> DetailedFramerate:
        """Build from skellycam's CurrentFramerate (pydantic, duck-typed)."""
        return cls(
            mean_frame_duration_ms=float(framerate.mean_frame_duration_ms),
            mean_frames_per_second=float(framerate.mean_frames_per_second),
            frame_duration_max=float(framerate.frame_duration_max),
            frame_duration_min=float(framerate.frame_duration_min),
            frame_duration_mean=float(framerate.frame_duration_mean),
            frame_duration_stddev=float(framerate.frame_duration_stddev),
            frame_duration_median=float(framerate.frame_duration_median),
            frame_duration_coefficient_of_variation=float(framerate.frame_duration_coefficient_of_variation),
            calculation_window_size=int(framerate.calculation_window_size),
            framerate_source=str(framerate.framerate_source),
        )


@dataclass(frozen=True, slots=True)
class FramerateMessage(MessageEnvelope):
    kind: ClassVar[MessageKind] = MessageKind.FRAMERATE
    camera_group_id: str = ""
    backend_framerate: DetailedFramerate = field(default_factory=DetailedFramerate)
    frontend_framerate: DetailedFramerate = field(default_factory=DetailedFramerate)


@dataclass(frozen=True, slots=True)
class CameraGroupSnapshot:
    id: str = ""
    configs: dict[str, Any] = field(default_factory=dict)
    cameras: dict[str, Any] = field(default_factory=dict)
    alive: bool = False
    recording_in_progress: bool = False
    paused: bool = False


@dataclass(frozen=True, slots=True)
class RealtimePipelineSnapshot:
    id: str = ""
    camera_group_id: str = ""
    camera_ids: tuple[str, ...] = ()
    alive: bool = False


@dataclass(frozen=True, slots=True)
class AppStateSnapshot:
    camera_groups: dict[str, CameraGroupSnapshot] = field(default_factory=dict)
    realtime_pipelines: tuple[RealtimePipelineSnapshot, ...] = ()

    @classmethod
    def from_state_dict(cls, state: dict[str, Any]) -> AppStateSnapshot:
        """Build from FreemocapApplication.to_state_dict() (nested dicts)."""
        camera_groups = {
            group_id: CameraGroupSnapshot(
                id=str(group.get("id", group_id)),
                configs=dict(group.get("configs", {})),
                cameras=dict(group.get("cameras", {})),
                alive=bool(group.get("alive", False)),
                recording_in_progress=bool(group.get("recording_in_progress", False)),
                paused=bool(group.get("paused", False)),
            )
            for group_id, group in state.get("camera_groups", {}).items()
        }
        realtime_pipelines = tuple(
            RealtimePipelineSnapshot(
                id=str(pipeline.get("id", "")),
                camera_group_id=str(pipeline.get("camera_group_id", "")),
                camera_ids=tuple(pipeline.get("camera_ids", ())),
                alive=bool(pipeline.get("alive", False)),
            )
            for pipeline in state.get("realtime_pipelines", [])
        )
        return cls(camera_groups=camera_groups, realtime_pipelines=realtime_pipelines)


@dataclass(frozen=True, slots=True)
class AppStateMessage(MessageEnvelope):
    kind: ClassVar[MessageKind] = MessageKind.APP_STATE
    server_pid: int = 0
    state: AppStateSnapshot = field(default_factory=AppStateSnapshot)

    @classmethod
    def from_state_dict(cls, *, server_pid: int, state: dict[str, Any]) -> AppStateMessage:
        return cls(server_pid=server_pid, state=AppStateSnapshot.from_state_dict(state))


@dataclass(frozen=True, slots=True)
class ProgressMessage(MessageEnvelope):
    kind: ClassVar[MessageKind] = MessageKind.PROGRESS
    pipeline_id: str = ""
    pipeline_type: str = ""
    phase: str = ""
    progress_fraction: float = 0.0
    detail: str = ""
    recording_name: str = ""
    recording_path: str = ""
    camera_id: str | None = None  # optional (video-node progress only)

    @classmethod
    def from_pipeline_progress(cls, progress: Any) -> ProgressMessage:
        """Build from PipelineProgressMessage (dataclass, duck-typed)."""
        return cls(
            pipeline_id=str(progress.pipeline_id),
            pipeline_type=str(progress.pipeline_type),
            phase=str(progress.phase),
            progress_fraction=float(progress.progress_fraction),
            detail=str(progress.detail),
            recording_name=str(progress.recording_name),
            recording_path=str(progress.recording_path),
            camera_id=getattr(progress, "camera_id", None),
        )


# ── Serialization (dataclass -> CBOR map -> bytes) ──────────────────────

def _cbor_value(value: Any) -> Any:
    """Convert a dataclass field value to a cbor2-encodable value."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, int, float, bool, bytes)):
        return value
    if isinstance(value, (tuple, list)):
        return [_cbor_value(v) for v in value]
    if isinstance(value, dict):
        return {key: _cbor_value(v) for key, v in value.items()}
    if is_dataclass(value):
        return _dataclass_cbor_map(value)
    raise TypeError(f"cannot encode {type(value).__name__}")


def _dataclass_cbor_map(obj: Any) -> dict[str, Any]:
    """Walk a dataclass's fields in declaration order; omit None-valued
    optional fields. A MessageEnvelope prepends its ClassVar kind."""
    result: dict[str, Any] = {}
    if isinstance(obj, MessageEnvelope):
        result["kind"] = obj.kind
    for f in fields(obj):
        value = getattr(obj, f.name)
        if value is None:
            continue
        result[f.name] = _cbor_value(value)
    return result


def to_cbor_map(message: MessageEnvelope) -> dict[str, Any]:
    """The cbor2-encodable map for one message, in documented field order."""
    return _dataclass_cbor_map(message)


def encode_message(message: MessageEnvelope) -> bytes:
    """Serialize one message to CBOR bytes (one message per socket write)."""
    return cbor2.dumps(to_cbor_map(message))
