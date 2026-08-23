"""The self-describing message model (frozen slots dataclasses + CBOR codec).

Every wire message is a frozen-slots dataclass that COMPOSES a MessageEnvelope
(version / timestamp / sequence) and declares a ClassVar "kind" discriminator.
There is no base class: the Message Protocol is the structural contract, and
encode_message is the single serialization gate (composition over inheritance).

The frame message is a fully self-contained document: convention, calibrated
cameras, model definitions, per-frame model instances, tracker observations,
and the image - a single frame decodes with zero prior state. Rendering bones
joins channel rows by index against the model's ordered symbol tables.

to_cbor_message() returns plain CBOR-encodable types (dict/list/scalar) - no
cbor2 import. Only encode_message touches cbor2.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum, StrEnum
from typing import Any, ClassVar, Protocol, runtime_checkable

import cbor2
from skellycam.core.types.type_overloads import (
    CameraGroupIdString,
    CameraIdString,
    CameraIndexInt,
)
from freemocap.core.streaming.rest_geometry import (
    PrimaryAxis,
    RestLandmark,
    RestSegment,
)
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from skellycam.core.recorders.framerate_tracker import CurrentFramerate
from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition
from freemocap.core.pipeline.posthoc.progress_messages import PipelineProgressMessage

CURRENT_VERSION: int = 0


class MessageKind(StrEnum):
    FRAME = "frame"
    LOG = "log"
    FRAMERATE = "framerate"
    APP_STATE = "app_state"
    PROGRESS = "progress"


class ChannelKind(StrEnum):
    KEYPOINTS_3D = "KEYPOINTS_3D"
    LANDMARKS_3D = "LANDMARKS_3D"
    SEGMENT_ORIGINS = "SEGMENT_ORIGINS"
    ROTATIONS_LOCAL = "ROTATIONS_LOCAL"
    ROTATIONS_WORLD = "ROTATIONS_WORLD"
    DERIVED_POINTS = "DERIVED_POINTS"
    OVERLAY_2D = "OVERLAY_2D"
    SEGMENT_LENGTHS = "SEGMENT_LENGTHS"
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


class CameraRotation(StrEnum):
    NONE = "none"
    CLOCKWISE_90 = "clockwise_90"
    ROTATE_180 = "rotate_180"
    COUNTERCLOCKWISE_90 = "counterclockwise_90"


# - Envelope (composed, not inherited) -

@dataclass(frozen=True, slots=True)
class MessageEnvelope:
    """The shared identity/ordering metadata every message composes."""

    version: int = CURRENT_VERSION
    timestamp: float = 0.0
    sequence: int = 0

    def to_cbor_message(self) -> dict[str, Any]:
        return {"version": self.version, "timestamp": self.timestamp, "sequence": self.sequence}


@runtime_checkable
class Message(Protocol):
    """The structural contract every wire message satisfies (no inheritance)."""

    kind: ClassVar[MessageKind]
    envelope: MessageEnvelope


# - Frame payload dataclasses -

@dataclass(frozen=True, slots=True)
class CoordinateConvention:
    units: Units = Units.MILLIMETERS
    handedness: Handedness = Handedness.RIGHT
    up_axis: Axis = Axis.PLUS_Z
    forward_axis: Axis = Axis.PLUS_Y
    rotation_frame: RotationFrame = RotationFrame.LOCAL
    rotation_form: RotationForm = RotationForm.QUATERNION

    def to_cbor_message(self) -> dict[str, str]:
        return {
            "units": self.units.value,
            "handedness": self.handedness.value,
            "up_axis": self.up_axis.value,
            "forward_axis": self.forward_axis.value,
            "rotation_frame": self.rotation_frame.value,
            "rotation_form": self.rotation_form.value,
        }


@dataclass(frozen=True, slots=True)
class CameraIntrinsicsMessage:
    fx: float
    fy: float
    cx: float
    cy: float
    k1: float = 0.0
    k2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0

    @classmethod
    def from_camera_intrinsics(cls, intrinsics: CameraIntrinsics) -> "CameraIntrinsicsMessage":
        return cls(
            fx=float(intrinsics.fx),
            fy=float(intrinsics.fy),
            cx=float(intrinsics.cx),
            cy=float(intrinsics.cy),
            k1=float(intrinsics.k1),
            k2=float(intrinsics.k2),
            p1=float(intrinsics.p1),
            p2=float(intrinsics.p2),
        )

    def to_cbor_message(self) -> dict[str, float]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True, slots=True)
class CameraExtrinsicsMessage:
    quaternion_wxyz: tuple[float, float, float, float]
    translation: tuple[float, float, float]

    @classmethod
    def from_camera_extrinsics(cls, extrinsics: CameraExtrinsics) -> "CameraExtrinsicsMessage":
        return cls(
            quaternion_wxyz=tuple(float(c) for c in extrinsics.quaternion_wxyz),
            translation=tuple(float(c) for c in extrinsics.translation),
        )

    def to_cbor_message(self) -> dict[str, Any]:
        return {"quaternion_wxyz": list(self.quaternion_wxyz), "translation": list(self.translation)}


@dataclass(frozen=True, slots=True)
class CalibratedCamera:
    """One calibrated camera on the wire.

    ``rotation`` + ``image_size`` define the ROTATED image coordinate space: the
    2D overlay points and the JPEG both live in this space (the backend rotates
    the image once, per the live camera config, before tracking and encoding), so
    a consumer scales overlays by ``image_size`` and needs no separate rotation.
    ``intrinsics``/``extrinsics`` are the calibration for that same rotated space.
    """

    id: CameraIdString
    index: CameraIndexInt
    rotation: CameraRotation
    image_size: tuple[int, int]
    intrinsics: CameraIntrinsicsMessage
    extrinsics: CameraExtrinsicsMessage
    world_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    world_orientation: tuple[tuple[float, float, float], ...] = ()

    @classmethod
    def from_camera_model(
        cls,
        camera_model: CameraModel,
        *,
        camera_id: CameraIdString,
        rotation: CameraRotation,
        image_size: tuple[int, int],
    ) -> "CalibratedCamera":
        return cls(
            id=CameraIdString(camera_id),
            index=CameraIndexInt(camera_model.index),
            rotation=rotation,
            image_size=(int(image_size[0]), int(image_size[1])),
            intrinsics=CameraIntrinsicsMessage.from_camera_intrinsics(camera_model.intrinsics),
            extrinsics=CameraExtrinsicsMessage.from_camera_extrinsics(camera_model.extrinsics),
            world_position=tuple(float(c) for c in camera_model.world_position),
            world_orientation=tuple(tuple(float(v) for v in row) for row in camera_model.world_orientation),
        )

    def to_cbor_message(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "rotation": self.rotation.value,
            "image_size": list(self.image_size),
            "intrinsics": self.intrinsics.to_cbor_message(),
            "extrinsics": self.extrinsics.to_cbor_message(),
            "world_position": list(self.world_position),
            "world_orientation": [list(row) for row in self.world_orientation],
        }


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    """One model definition (the standard human), shared by its instances."""

    model_id: str
    segments: tuple[RestSegment, ...]
    landmarks: tuple[RestLandmark, ...]

    @classmethod
    def from_standard_human(
        cls, skeleton: SkeletonDefinition, rest_pose: RestPose
    ) -> "ModelDefinition":
        return cls(
            model_id="standard_human",
            segments=tuple(
                RestSegment(
                    name=segment.name,
                    parent=rest_pose.parents[segment.name],
                    primary_axis=PrimaryAxis.from_spatial_axis(
                        segment.frame_definition.primary_axis
                    ),
                    rest_orientation=tuple(
                        float(c)
                        for c in rest_pose.segment_orientations[segment.name].as_array()
                    ),
                    length_mm=float(segment.length),
                    is_fully_specified=segment.is_fully_specified,
                )
                for segment in skeleton.segments.values()
            ),
            landmarks=tuple(
                RestLandmark(
                    name=name,
                    rest_position=tuple(
                        float(c) for c in rest_pose.landmark_positions[name].array
                    ),
                )
                for name in skeleton.landmarks
            ),
        )

    def to_cbor_message(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "segments": [s.to_cbor_message() for s in self.segments],
            "landmarks": [l.to_cbor_message() for l in self.landmarks],
        }


@dataclass(frozen=True, slots=True)
class ChannelBlock:
    """One index-keyed column block: kind + columns + data (packed float32
    little-endian bytes, columns by names, row-major). Row labels are the
    model's ordered segments/landmarks (index-keyed); tracker-keypoint channels
    carry their tracker names inline via names. camera_id is present
    only on per-camera overlay channels."""

    kind: ChannelKind
    columns: tuple[str, ...]
    data: bytes
    camera_id: CameraIdString | None = None
    names: tuple[str, ...] | None = None
    # Full-resolution (rotated) image size of the channel's coordinate space,
    # carried on per-camera overlay channels so the consumer can scale overlay
    # points without depending on a calibration entry existing for the camera.
    image_size: tuple[int, int] | None = None

    @classmethod
    def from_float32_rows(
        cls,
        *,
        kind: ChannelKind,
        columns: tuple[str, ...],
        rows: list[list[float]],
        camera_id: CameraIdString | None = None,
        names: tuple[str, ...] | None = None,
    ) -> "ChannelBlock":
        packed = bytearray()
        for row in rows:
            packed += struct.pack(f"<{len(row)}f", *row)
        return cls(kind=kind, columns=tuple(columns), data=bytes(packed), camera_id=camera_id, names=names)


@dataclass(frozen=True, slots=True)
class ModelInstance:
    """One per-frame instance of a model definition."""

    instance_id: int
    model_id: str
    channels: tuple[ChannelBlock, ...]


@dataclass(frozen=True, slots=True)
class TrackerObservation:
    """One tracker's per-frame observation: its keypoint channels. model_id names
    the model whose landmarks this tracker's keypoints hydrate; the keypoint->landmark
    mapping is deferred (the client already receives pre-hydrated landmarks)."""

    tracker_id: str
    detector_type: str
    model_id: str
    channels: tuple[ChannelBlock, ...]


# - Frame kind -

@dataclass(frozen=True, slots=True)
class FrameMessage:
    kind: ClassVar[MessageKind] = MessageKind.FRAME
    envelope: MessageEnvelope = field(default_factory=MessageEnvelope)
    frame_number: int = 0
    model_sequence: int = 0
    convention: CoordinateConvention = field(default_factory=CoordinateConvention)
    cameras: tuple[CalibratedCamera, ...] = ()
    models: tuple[ModelDefinition, ...] = ()
    instances: tuple[ModelInstance, ...] = ()
    trackers: tuple[TrackerObservation, ...] = ()
    image: bytes | None = None


# - Append / telemetry kinds -

@dataclass(frozen=True, slots=True)
class LogRecord:
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
    def from_logging_dict(cls, record: dict[str, Any]) -> "LogRecord":
        known = {f.name for f in fields(cls)}
        kwargs = {key: value for key, value in record.items() if key in known}
        # The websocket log queue emits ``args`` as a list (the args are already
        # baked into the message); the frozen dataclass declares a tuple and
        # beartype enforces the hint strictly, so coerce it here.
        if "args" in kwargs and not isinstance(kwargs["args"], tuple):
            kwargs["args"] = tuple(kwargs["args"])
        return cls(**kwargs)


@dataclass(frozen=True, slots=True)
class LogMessage:
    kind: ClassVar[MessageKind] = MessageKind.LOG
    envelope: MessageEnvelope = field(default_factory=MessageEnvelope)
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
    def from_current_framerate(cls, framerate: CurrentFramerate) -> "DetailedFramerate":
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
class FramerateMessage:
    kind: ClassVar[MessageKind] = MessageKind.FRAMERATE
    envelope: MessageEnvelope = field(default_factory=MessageEnvelope)
    camera_group_id: CameraGroupIdString = ""
    backend_framerate: DetailedFramerate = field(default_factory=DetailedFramerate)
    frontend_framerate: DetailedFramerate = field(default_factory=DetailedFramerate)


@dataclass(frozen=True, slots=True)
class CameraGroupSnapshot:
    id: CameraGroupIdString = ""
    configs: dict[str, Any] = field(default_factory=dict)
    cameras: dict[CameraIdString, Any] = field(default_factory=dict)
    alive: bool = False
    recording_in_progress: bool = False
    paused: bool = False


@dataclass(frozen=True, slots=True)
class RealtimePipelineSnapshot:
    id: str = ""
    camera_group_id: CameraGroupIdString = ""
    camera_ids: tuple[CameraIdString, ...] = ()
    alive: bool = False


@dataclass(frozen=True, slots=True)
class AppStateSnapshot:
    camera_groups: dict[CameraGroupIdString, CameraGroupSnapshot] = field(default_factory=dict)
    realtime_pipelines: tuple[RealtimePipelineSnapshot, ...] = ()

    @classmethod
    def from_state_dict(cls, state: dict[str, Any]) -> "AppStateSnapshot":
        camera_groups = {
            CameraGroupIdString(group_id): CameraGroupSnapshot(
                id=CameraGroupIdString(group.get("id", group_id)),
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
                camera_group_id=CameraGroupIdString(pipeline.get("camera_group_id", "")),
                camera_ids=tuple(CameraIdString(c) for c in pipeline.get("camera_ids", ())),
                alive=bool(pipeline.get("alive", False)),
            )
            for pipeline in state.get("realtime_pipelines", [])
        )
        return cls(camera_groups=camera_groups, realtime_pipelines=realtime_pipelines)


@dataclass(frozen=True, slots=True)
class AppStateMessage:
    kind: ClassVar[MessageKind] = MessageKind.APP_STATE
    envelope: MessageEnvelope = field(default_factory=MessageEnvelope)
    server_pid: int = 0
    state: AppStateSnapshot = field(default_factory=AppStateSnapshot)

    @classmethod
    def from_state_dict(cls, *, server_pid: int, state: dict[str, Any]) -> "AppStateMessage":
        return cls(server_pid=server_pid, state=AppStateSnapshot.from_state_dict(state))


@dataclass(frozen=True, slots=True)
class ProgressMessage:
    kind: ClassVar[MessageKind] = MessageKind.PROGRESS
    envelope: MessageEnvelope = field(default_factory=MessageEnvelope)
    pipeline_id: str = ""
    pipeline_type: str = ""
    phase: str = ""
    progress_fraction: float = 0.0
    detail: str = ""
    recording_name: str = ""
    recording_path: str = ""
    camera_id: CameraIdString | None = None

    @classmethod
    def from_pipeline_progress(cls, progress: PipelineProgressMessage) -> "ProgressMessage":
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


# - Serialization -

def _cbor_value(value: Any) -> Any:
    """Recursively convert a value to its CBOR-encodable form, respecting each
    dataclass's to_cbor_message() method where present."""
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
        serializer = getattr(value, "to_cbor_message", None)
        if callable(serializer):
            return _cbor_value(serializer())
        result: dict[str, Any] = {}
        for f in fields(value):
            v = getattr(value, f.name)
            if v is not None:
                result[f.name] = _cbor_value(v)
        return result
    raise TypeError(f"cannot encode {type(value).__name__}")


def encode_message(message: Message) -> bytes:
    """Serialize one message to CBOR bytes. Flattens the composed envelope
    (kind + version + timestamp + sequence) before the payload fields."""
    if not isinstance(message, Message):
        raise TypeError(f"{type(message).__name__} is not a Message (missing kind/envelope)")
    result: dict[str, Any] = {"kind": message.kind.value}
    result.update(message.envelope.to_cbor_message())
    for f in fields(message):
        if f.name in ("kind", "envelope"):
            continue
        value = getattr(message, f.name)
        if value is not None:
            result[f.name] = _cbor_value(value)
    return cbor2.dumps(result)
