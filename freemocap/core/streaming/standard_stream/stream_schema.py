"""The standard-stream ``stream_schema`` (StreamInfo) — the static descriptor.

Sent once (JSON) on connect and again only when it changes. It declares the
channel layout so per-frame samples carry no names: the ordered ``channels``
*are* the sample layout — the decoder maps each block back to its group by
``block_kind`` (and ``camera_id`` for OVERLAY_2D).

Stream dimensions (subjects, cameras) are fixed at stream creation; a topology
change tears down and rebuilds the stream with a new schema (schema-on-change).

SSOT for the wire contract:
[09 — Standard Stream Protocol](docs/streaming-compatibility/09-standard-stream-protocol.md).
"""
from __future__ import annotations

import enum
from collections.abc import Sequence

import msgspec

from freemocap.core.streaming.standard_stream.coordinate_convention import (
    FREEMOCAP_CANONICAL_CONVENTION,
    CoordinateConvention,
)
from skellyforge.skellymodels.standard_human.standard_human_model import (
    StandardHuman,
)

# ── Column layouts — SSOT alongside the wire contract ─────────────────────
SKELETON_POINT_COLUMNS = ("x", "y", "z", "reprojection_error")
DERIVED_POINT_COLUMNS = ("x", "y", "z")
ROTATION_COLUMNS = ("w", "x", "y", "z")
OVERLAY_2D_COLUMNS = ("x", "y", "visibility")

DEFAULT_DERIVED_POINTS = ("center_of_mass", "xcom")


class ChannelKind(enum.IntEnum):
    """The kinds of channel group (and block). Wire value = the block_kind byte."""

    POINTS = 0      # 3D points — skeleton landmarks + derived points (center_of_mass, xcom).
                    # columns e.g. (x, y, z, reprojection_error); a group may omit the error column.
    ROTATIONS = 1   # LEGACY generic rotation channel — replaced by ROTATIONS_WORLD + ROTATIONS_LOCAL.
                    # Kept for backward-compat during transition.
    OVERLAY_2D = 2  # per-camera 2D projection — columns (x, y, visibility); one block per camera
    ROTATIONS_WORLD = 3  # per-bone world-frame quaternion — columns (w, x, y, z)
    ROTATIONS_LOCAL = 4  # per-bone parent-relative quaternion — columns (w, x, y, z)


class ChannelGroup(msgspec.Struct, frozen=True):
    """One ordered group of channels: which entities, which columns, what units."""

    kind: ChannelKind
    names: tuple[str, ...]    # canonical landmark / segment names
    columns: tuple[str, ...]  # per-element columns, e.g. ("x", "y", "z", "reprojection_error")
    units: str


class RestPose(msgspec.Struct, frozen=True):
    """The declared T-pose: identity rotation == this pose.

    Populated by the canonical human model. Orientations are wxyz quaternions.
    """

    positions: dict[str, tuple[float, float, float]] = msgspec.field(default_factory=dict)
    reference_orientations: dict[str, tuple[float, float, float, float]] = msgspec.field(default_factory=dict)

    @classmethod
    def from_standard_human(cls, standard_human: StandardHuman) -> RestPose:
        """Build the rest pose from the canonical model's T-pose.

        Joint center positions come from the model's T-pose markers (proximal
        joint centers, keyed by bone name). Orientations are identity
        quaternions — by contract, identity quaternion == T-pose.
        """
        positions: dict[str, tuple[float, float, float]] = {}
        for name, pos in standard_human.t_pose_markers.items():
            positions[name] = (float(pos[0]), float(pos[1]), float(pos[2]))

        identity = (1.0, 0.0, 0.0, 0.0)
        reference_orientations = {name: identity for name in standard_human.bone_names}

        return cls(positions=positions, reference_orientations=reference_orientations)


class StreamSchema(msgspec.Struct):
    """The full static descriptor for one standard stream (one subject's layout)."""

    stream_id: str    # unique (uuid-derived) — the key everything is addressed by
    stream_name: str  # human-facing label; not required to be unique
    coordinate_convention: CoordinateConvention
    channels: tuple[ChannelGroup, ...]
    connections: tuple[tuple[str, str], ...] = ()
    joint_hierarchy: dict[str, tuple[str, ...]] = msgspec.field(default_factory=dict)
    rest_pose: RestPose | None = None
    camera_ids: tuple[str, ...] = ()  # cameras for OVERLAY_2D — fixed at stream creation
    max_persons: int = 1   # reserved for multi-subject; 1 for now
    message_type: str = "stream_schema"

    @classmethod
    def from_standard_human(
        cls,
        *,
        stream_id: str,
        stream_name: str,
        standard_human: StandardHuman,
        camera_ids: Sequence[str] = (),
        convention: CoordinateConvention = FREEMOCAP_CANONICAL_CONVENTION,
        derived_point_names: Sequence[str] = DEFAULT_DERIVED_POINTS,
        max_persons: int = 1,
    ) -> StreamSchema:
        """Build the standard-stream schema from the canonical human model.

        Enumerates channels in fixed order (decoder indexes blocks by position):

        0. **SKELETON_POINTS** — bone proximal joint centers,
           columns ``(x, y, z, reprojection_error)``.
        1. **DERIVED_POINTS** — ``center_of_mass``, ``xcom``;
           columns ``(x, y, z)`` (no per-point reprojection error).
        2. **ROTATIONS_WORLD** — per-bone world-frame quaternion,
           columns ``(w, x, y, z)``.
        3. **ROTATIONS_LOCAL** — per-bone parent-relative quaternion,
           columns ``(w, x, y, z)``.
        4. **OVERLAY_2D** — one block per camera in the sample,
           columns ``(x, y, visibility)``, keyed by ``camera_id``.

        ``connections`` and ``joint_hierarchy`` are derived from the bone
        hierarchy. ``rest_pose`` carries T-pose positions + identity
        orientations.
        """
        bone_names = tuple(standard_human.bone_names)
        units = convention.units.value

        # ── Channel groups (fixed order) ──────────────────────────────
        channels: tuple[ChannelGroup, ...] = (
            ChannelGroup(
                kind=ChannelKind.POINTS,
                names=bone_names,
                columns=SKELETON_POINT_COLUMNS,
                units=units,
            ),
            ChannelGroup(
                kind=ChannelKind.POINTS,
                names=tuple(derived_point_names),
                columns=DERIVED_POINT_COLUMNS,
                units=units,
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS_WORLD,
                names=bone_names,
                columns=ROTATION_COLUMNS,
                units="quaternion",
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS_LOCAL,
                names=bone_names,
                columns=ROTATION_COLUMNS,
                units="quaternion",
            ),
            ChannelGroup(
                kind=ChannelKind.OVERLAY_2D,
                names=bone_names,
                columns=OVERLAY_2D_COLUMNS,
                units="px",
            ),
        )

        # ── Connections: parent→child bone edges ──────────────────────
        connections: list[tuple[str, str]] = []
        for bone in standard_human.bones:
            for child in standard_human.get_children(bone.name):
                connections.append((bone.name, child.name))

        # ── Joint hierarchy ───────────────────────────────────────────
        hierarchy: dict[str, tuple[str, ...]] = {}
        for key, children in standard_human.joint_hierarchy.items():
            hierarchy[key] = tuple(children)

        rest_pose = RestPose.from_standard_human(standard_human)

        return cls(
            stream_id=stream_id,
            stream_name=stream_name,
            coordinate_convention=convention,
            channels=channels,
            connections=tuple(connections),
            joint_hierarchy=hierarchy,
            rest_pose=rest_pose,
            camera_ids=tuple(camera_ids),
            max_persons=max_persons,
        )


_ENCODER = msgspec.json.Encoder()


def encode_schema(schema: StreamSchema) -> bytes:
    """Serialize a schema to JSON bytes (sent once on connect / on change)."""
    return _ENCODER.encode(schema)


def decode_schema(data: bytes) -> StreamSchema:
    """Reconstruct a schema from JSON bytes."""
    return msgspec.json.decode(data, type=StreamSchema)
