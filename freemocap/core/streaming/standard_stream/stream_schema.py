"""The standard-stream ``stream_schema`` (StreamInfo) — the static descriptor.

Sent once (JSON) on connect and again only when it changes. It declares the
channel layout so per-frame samples carry no names: the ordered ``channels``
*are* the sample layout — the decoder maps each block back to its group by
``block_kind`` (and ``camera_id`` / ``overlay_layer`` for OVERLAY_2D).

Stream dimensions (subjects, cameras) are fixed at stream creation; a topology
change tears down and rebuilds the stream with a new schema (schema-on-change).

SSOT for the wire contract:
`current-work-plans/03-transport/standard-stream-protocol.md`.
"""
from __future__ import annotations

import enum

import msgspec

from freemocap.core.streaming.standard_stream.coordinate_convention import (
    CoordinateConvention,
)
from freemocap.core.types.type_overloads import SegmentNameString  # noqa: TC001 — msgspec resolves this at class-def time for ``segment_parents``
from skellyforge.kinematics.quaternion_math import RotationQuaternion
from skellyforge.skellymodels.standard_human.reference_geometry import (
    build_reference_geometry,
)
from skellyforge.skellymodels.standard_human.standard_human_model import (
    StandardHuman,  # noqa: TC002 — beartype resolves this in the RestPose/merge-helper signatures at runtime
)

from freemocap.core.streaming.constants import (  # noqa: E402  # after the module docstring — see the header note
    NOMINAL_SUBJECT_HEIGHT_MM,
)


def _merge_segment_lengths(
    standard_human: StandardHuman,
) -> dict[str, float]:
    """The anthropometric default per-segment rest lengths.

    The schema carries defaults (``length_ratio × NOMINAL_SUBJECT_HEIGHT_MM``)
    so a consumer can render before the first sample arrives; the live measured
    estimates ride the per-frame ``SEGMENT_LENGTHS`` block and never touch the
    schema. Shared by the rest-pose build and the schema's ``segment_lengths``
    field.
    """
    return {
        segment.name: segment.length_ratio * NOMINAL_SUBJECT_HEIGHT_MM
        for segment in standard_human.segments
    }


# ── Column layouts — SSOT alongside the wire contract ─────────────────────
KEYPOINTS_3D_COLUMNS = ("x", "y", "z", "reprojection_error")
SEGMENT_ORIGINS_COLUMNS = ("x", "y", "z")
DERIVED_POINT_COLUMNS = ("x", "y", "z")
ROTATION_COLUMNS = ("w", "x", "y", "z")
OVERLAY_2D_COLUMNS = ("x", "y", "visibility")
SEGMENT_LENGTHS_COLUMNS = ("length_mm",)
IMAGE_JPEG_COLUMNS = ("jpeg_bytes",)

DEFAULT_DERIVED_POINTS = ("center_of_mass", "xcom")


class ChannelKind(enum.IntEnum):
    """The kinds of channel group (and block). Wire value = the block_kind byte.

    One member per channel group — no generic ``ROTATIONS`` kind (a rotation
    that doesn't declare its frame is exactly the ambiguity the convention
    exists to prevent). See 07 § Segment rotation conventions.
    """

    KEYPOINTS_3D = 0        # tracker-named measured keypoints — columns (x, y, z, reprojection_error)
    LANDMARKS_3D = 1        # the 76 hydrated standard-human landmarks — columns (x, y, z, reprojection_error)
    SEGMENT_ORIGINS = 2     # fitted segment transform origins — columns (x, y, z)
    ROTATIONS_LOCAL = 3     # per-segment parent-relative quaternion — columns (w, x, y, z)
    ROTATIONS_WORLD = 4     # per-segment world-frame quaternion — columns (w, x, y, z)
    DERIVED_POINTS = 5      # whole-body kinematics (center_of_mass, xcom) — columns (x, y, z)
    OVERLAY_2D = 6          # per-camera 2D projection — columns (x, y, visibility); keyed by (camera_id, overlay_layer)
    SEGMENT_LENGTHS = 7     # per-segment rest length (mm), sent every frame — columns (length_mm,)
    IMAGE_JPEG = 8          # camera images — a uint8 block (dtype_code UINT8). Currently ONE opaque
                            # multi-camera JPEG blob (the SkellyCam frontend payload; the consumer splits
                            # it per camera). TODO: split into per-camera IMAGE_JPEG blocks, symmetric with
                            # OVERLAY_2D, once the SkellyCam payload is unpacked backend-side.
    OVERLAY_REPROJECTIONS = 9  # per-camera 2D segment-origin landmarks — the fitted skeleton projected
                               # back into each camera (capture-resolution px). Columns (x, y, visibility),
                               # keyed by camera_id; names are the 60 segment names. Empty (NaN) rows when
                               # there is no valid calibration / no solve this frame.


class OverlayLayer(enum.IntEnum):
    """Which half of a camera's OVERLAY_2D block (given ``camera_id``).

    The integer value is the ``overlay_layer`` byte on the wire (block header).
    """

    DETECTIONS = 0         # tracker keypoints as seen in that camera's image
    REPROJECTIONS = 1      # the fitted segment model projected back into that camera


class ChannelGroup(msgspec.Struct, frozen=True):
    """One ordered group of channels: which entities, which columns, what units."""

    kind: ChannelKind
    names: tuple[str, ...]    # keypoint or segment names
    columns: tuple[str, ...]  # per-element columns, e.g. ("x", "y", "z", "reprojection_error")
    units: str


class RestPose(msgspec.Struct, frozen=True):
    """The declared T-pose the live pose is measured against.

    positions — rest landmark positions (mm), one per schematic keypoint.
    orientations — per-segment rest-frame orientation (wxyz): the rotation
    mapping the segment's LOCAL frame to its world-frame T-pose. The solver
    measures ROTATIONS_WORLD *relative to* this rest frame, so at T-pose
    ROTATIONS_WORLD is identity — but the rest frame itself is NOT the
    identity: a body segment's +Y points toward its child (the spine's +Y is
    world +Z, up). A consumer renders a segment by composing this rest
    orientation (and its long-axis name, segment_axes) before applying
    ROTATIONS_WORLD.
    """

    positions: dict[str, tuple[float, float, float]] = msgspec.field(default_factory=dict)
    orientations: dict[str, tuple[float, float, float, float]] = msgspec.field(default_factory=dict)

    @classmethod
    def from_standard_human(
        cls,
        standard_human: StandardHuman,
    ) -> RestPose:
        """Build the rest pose from the standard human model's T-pose.

        Positions come from the model's reference geometry (rest landmark
        positions, keyed by landmark name) at the anthropometric default
        lengths. Orientations are the per-segment rest-frame rotations
        (reference_geometry basis → quaternion, local→world). The live measured
        lengths ride the per-frame SEGMENT_LENGTHS block, not the rest pose.
        """
        merged = _merge_segment_lengths(standard_human)
        geometry = build_reference_geometry(list(standard_human.segments), merged)

        positions: dict[str, tuple[float, float, float]] = {}
        for name, pos in geometry.landmarks.items():
            positions[name] = (float(pos[0]), float(pos[1]), float(pos[2]))

        orientations: dict[str, tuple[float, float, float, float]] = {}
        for segment in standard_human.segments:
            q = RotationQuaternion.from_rotation_matrix(
                geometry.segments[segment.name].basis.T
            )
            orientations[segment.name] = (
                float(q.w),
                float(q.x),
                float(q.y),
                float(q.z),
            )

        return cls(positions=positions, orientations=orientations)


class StreamSchema(msgspec.Struct, frozen=True):
    """The full static descriptor for one standard stream (one subject's layout).

    Immutable (frozen): a schema is an immutable declaration, re-sent whole on
    change — never mutated in place.
    """

    stream_id: str    # unique (uuid-derived) — the key everything is addressed by
    stream_name: str  # human-facing label; not required to be unique
    coordinate_convention: CoordinateConvention
    channels: tuple[ChannelGroup, ...]
    connections: tuple[tuple[str, str], ...] = ()
    joint_hierarchy: dict[str, tuple[str, ...]] = msgspec.field(default_factory=dict)
    segment_parents: dict[SegmentNameString, SegmentNameString | None] = msgspec.field(default_factory=dict)
    # Per-segment long-axis basis name (the segment's EXACT axis declaration:
    # "x" | "y" | "z") — body/hand segments declare "y", face segments "z".
    # This names WHICH axis of the rest frame (rest_pose.orientations) is the
    # long axis; a consumer orients its geometry onto that axis, composes the
    # rest orientation, then applies ROTATIONS_WORLD.
    segment_axes: dict[str, str] = msgspec.field(default_factory=dict)
    rest_pose: RestPose | None = None
    # Per-segment rest lengths (mm), one entry per segment name — the
    # anthropometric defaults (a consumer renders before the first sample
    # arrives). The live measured estimates ride the per-frame SEGMENT_LENGTHS
    # block and never touch the schema.
    segment_lengths: dict[str, float] = msgspec.field(default_factory=dict)
    camera_ids: tuple[str, ...] = ()  # cameras for OVERLAY_2D — fixed at stream creation
    # Per-camera capture-resolution image size (width, height) in px — the
    # coordinate space of OVERLAY_2D values. Static per stream (camera-fixed);
    # consumers scale overlay points to their own display size with it.
    camera_image_sizes: dict[str, tuple[int, int]] = msgspec.field(default_factory=dict)
    max_persons: int = 1   # reserved for multi-subject; 1 for now
    message_type: str = "stream_schema"

_ENCODER = msgspec.json.Encoder()


def encode_schema(schema: StreamSchema) -> bytes:
    """Serialize a schema to JSON bytes (sent once on connect / on change)."""
    return _ENCODER.encode(schema)


def decode_schema(data: bytes) -> StreamSchema:
    """Reconstruct a schema from JSON bytes."""
    return msgspec.json.decode(data, type=StreamSchema)
