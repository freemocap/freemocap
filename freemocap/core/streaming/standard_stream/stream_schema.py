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
from collections.abc import Sequence  # noqa: TC003 — beartype resolves this in the ``from_standard_human`` signature at runtime

import msgspec

from freemocap.core.streaming.standard_stream.coordinate_convention import (
    FREEMOCAP_CANONICAL_CONVENTION,
    CoordinateConvention,
)
from freemocap.core.types.type_overloads import SegmentNameString  # noqa: TC001 — msgspec resolves this at class-def time for ``segment_parents``
from skellyforge.skellymodels.standard_human.reference_geometry import (
    build_reference_geometry,
)
from skellyforge.skellymodels.standard_human.standard_human_model import (
    StandardHuman,  # noqa: TC002 — beartype resolves this in the ``from_standard_human`` signature at runtime
)

# Nominal subject height (mm) used to convert each segment's ``length_ratio``
# (a fraction of standing height) into an absolute rest length. Single source
# shared by the schema's rest-pose build, the realtime aggregator, the
# RealtimeFilterConfig``height_mm`` default, and the skeleton rigidifier's
# length seeds.
NOMINAL_SUBJECT_HEIGHT_MM = 1750.0

def _merge_segment_lengths(
    standard_human: StandardHuman,
    measured_lengths: dict[str, float] | None,
) -> dict[str, float]:
    """Per-segment rest length: measured where available, anthropometric default otherwise.

    The schema's ``segment_lengths`` contract is *default-then-update*: on first
    send the mapping carries the anthropometric defaults (``length_ratio ×
    NOMINAL_SUBJECT_HEIGHT_MM``); whenever the rigifier's live measured
    estimates change materially, the server re-sends a schema whose
    ``measured_lengths`` override the measured segments and leave the rest at
    their defaults. This helper is the single point where a measured dict is
    merged over the defaults (shared by the rest-pose build and the
    ``segment_lengths`` field).
    """
    merged = {
        segment.name: segment.length_ratio * NOMINAL_SUBJECT_HEIGHT_MM
        for segment in standard_human.segments
    }
    if measured_lengths:
        for name, length in measured_lengths.items():
            merged[name] = float(length)
    return merged


# ── Column layouts — SSOT alongside the wire contract ─────────────────────
KEYPOINTS_3D_COLUMNS = ("x", "y", "z", "reprojection_error")
SEGMENT_ORIGINS_COLUMNS = ("x", "y", "z")
DERIVED_POINT_COLUMNS = ("x", "y", "z")
ROTATION_COLUMNS = ("w", "x", "y", "z")
OVERLAY_2D_COLUMNS = ("x", "y", "visibility")

DEFAULT_DERIVED_POINTS = ("center_of_mass", "xcom")


class ChannelKind(enum.IntEnum):
    """The kinds of channel group (and block). Wire value = the block_kind byte.

    One member per channel group — no generic ``ROTATIONS`` kind (a rotation
    that doesn't declare its frame is exactly the ambiguity the convention
    exists to prevent). See 07 § Segment rotation conventions.
    """

    KEYPOINTS_3D = 0        # triangulated tracker detections — columns (x, y, z, reprojection_error)
    SEGMENT_ORIGINS = 1     # fitted segment transform origins — columns (x, y, z)
    ROTATIONS_LOCAL = 2     # per-segment parent-relative quaternion — columns (w, x, y, z)
    ROTATIONS_WORLD = 3     # per-segment world-frame quaternion — columns (w, x, y, z)
    DERIVED_POINTS = 4      # whole-body kinematics (center_of_mass, xcom) — columns (x, y, z)
    OVERLAY_2D = 5          # per-camera 2D projection — columns (x, y, visibility); keyed by (camera_id, overlay_layer)


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
    """The declared T-pose: identity rotation == this pose.

    Populated by the canonical human model. Orientations are wxyz quaternions.
    """

    positions: dict[str, tuple[float, float, float]] = msgspec.field(default_factory=dict)
    reference_orientations: dict[str, tuple[float, float, float, float]] = msgspec.field(default_factory=dict)

    @classmethod
    def from_standard_human(
        cls,
        standard_human: StandardHuman,
        measured_lengths: dict[str, float] | None = None,
    ) -> RestPose:
        """Build the rest pose from the canonical model's T-pose.

        Joint center positions come from the model's reference geometry (rest
        keypoint positions, keyed by keypoint name). Orientations are identity
        quaternions — by contract, identity quaternion == T-pose.

        ``measured_lengths`` overrides individual segments' rest lengths; any
        segment NOT in the override falls back to its anthropometric default
        (``length_ratio × NOMINAL_SUBJECT_HEIGHT_MM``). The same merged lengths
        dict drives ``build_reference_geometry`` so the rest pose positions and
        the schema's ``segment_lengths`` stay consistent. See
        ``StreamSchema.from_standard_human`` for the default-then-update
        lifecycle.
        """
        merged = _merge_segment_lengths(standard_human, measured_lengths)
        geometry = build_reference_geometry(list(standard_human.segments), merged)

        positions: dict[str, tuple[float, float, float]] = {}
        for name, pos in geometry.keypoints.items():
            positions[name] = (float(pos[0]), float(pos[1]), float(pos[2]))

        identity = (1.0, 0.0, 0.0, 0.0)
        reference_orientations = {name: identity for name in standard_human.segment_names}

        return cls(positions=positions, reference_orientations=reference_orientations)


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
    rest_pose: RestPose | None = None
    # Per-segment rest lengths (mm), one entry per segment name. Default-then-
    # update lifecycle: anthropometric defaults on first send, then re-sent with
    # measured values when the live estimates change materially (see
    # ``from_standard_human``).
    segment_lengths: dict[str, float] = msgspec.field(default_factory=dict)
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
        measured_lengths: dict[str, float] | None = None,
    ) -> StreamSchema:
        """Build the standard-stream schema from the canonical human model.

        THIS function IS the boundary between the model and the wire. The
        coupling between the schema and ``StandardHuman`` is intended (D30):
        the composed model is the one source of the channel names, hierarchy,
        and rest pose. This module importing the model at module scope is that
        decision made concrete.

        Enumerates channels in fixed order (decoder indexes blocks by position):

        0. **KEYPOINTS_3D** — tracker keypoint names (76, sorted),
           columns ``(x, y, z, reprojection_error)``.
        1. **SEGMENT_ORIGINS** — segment names (60), transform origins,
           columns ``(x, y, z)``.
        2. **ROTATIONS_LOCAL** — segment names, parent-relative quaternion,
           columns ``(w, x, y, z)``.
        3. **ROTATIONS_WORLD** — segment names, world-frame quaternion,
           columns ``(w, x, y, z)``.
        4. **DERIVED_POINTS** — ``center_of_mass``, ``xcom``,
           columns ``(x, y, z)``.
        5. **OVERLAY_2D** — one block per camera per layer in the sample,
           columns ``(x, y, visibility)``, keyed by ``camera_id`` +
           ``overlay_layer``. ``names`` lists the DETECTIONS-layer keypoints
           (the detector's ``body``-stage 2D detections, NaN-padded); the
           REPROJECTIONS layer carries the same keypoint set (the fitted model
           projected back down), so ``names`` describes both layers' rows.

        ``segment_parents`` (segment → parent) and ``rest_pose`` together are
        what a consumer needs to compose the local-rotation chain into world
        placement — the VMC/VRM model.

        ``measured_lengths`` carries the live measured per-segment rest lengths
        (keyed by segment name) from the rigidifier. The schema's
        ``segment_lengths`` (and the rest pose, via the same merged dict) is the
        *default-then-update* lifecycle: without ``measured_lengths`` every
        segment takes its anthropometric default (``length_ratio ×
        NOMINAL_SUBJECT_HEIGHT_MM``); when the estimates change materially, the
        server calls this again with ``measured_lengths`` so only the measured
        segments are overridden and the rest stay at their defaults. The
        frontend therefore always has lengths — starting from human defaults and
        converging to the measured values over the stream.
        """
        segment_names = tuple(standard_human.segment_names)
        segment_lengths = _merge_segment_lengths(standard_human, measured_lengths)
        keypoint_names = tuple(sorted(standard_human.required_keypoints()))
        segment_parents: dict[SegmentNameString, SegmentNameString | None] = {
            name: parent for name, parent in standard_human.segment_parents.items()
        }
        units = convention.units.value

        # ── Channel groups (fixed order) ──────────────────────────────
        channels: tuple[ChannelGroup, ...] = (
            ChannelGroup(
                kind=ChannelKind.KEYPOINTS_3D,
                names=keypoint_names,
                columns=KEYPOINTS_3D_COLUMNS,
                units=units,
            ),
            ChannelGroup(
                kind=ChannelKind.SEGMENT_ORIGINS,
                names=segment_names,
                columns=SEGMENT_ORIGINS_COLUMNS,
                units=units,
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS_LOCAL,
                names=segment_names,
                columns=ROTATION_COLUMNS,
                units="quaternion",
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS_WORLD,
                names=segment_names,
                columns=ROTATION_COLUMNS,
                units="quaternion",
            ),
            ChannelGroup(
                kind=ChannelKind.DERIVED_POINTS,
                names=tuple(derived_point_names),
                columns=DERIVED_POINT_COLUMNS,
                units=units,
            ),
            ChannelGroup(
                kind=ChannelKind.OVERLAY_2D,
                names=keypoint_names,
                columns=OVERLAY_2D_COLUMNS,
                units="px",
            ),
        )

        # ── Connections: parent→child segment edges ──────────────────
        connections: list[tuple[str, str]] = []
        for segment in standard_human.segments:
            for child in standard_human.get_children(segment.name):
                connections.append((segment.name, child.name))

        rest_pose = RestPose.from_standard_human(standard_human, measured_lengths)

        return cls(
            stream_id=stream_id,
            stream_name=stream_name,
            coordinate_convention=convention,
            channels=channels,
            connections=tuple(connections),
            joint_hierarchy={k: tuple(v) for k, v in standard_human.joint_hierarchy.items()},
            segment_parents=segment_parents,
            rest_pose=rest_pose,
            segment_lengths=segment_lengths,
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
