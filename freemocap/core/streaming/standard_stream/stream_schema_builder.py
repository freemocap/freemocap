"""Build a ``StreamSchema`` from a canonical human model + topology.

The pure builder (``build_stream_schema``) takes plain canonical data (landmark
names, segments, connections, hierarchy) plus the camera/convention topology and
produces the WS-1 ``StreamSchema``. A thin SkellyForge adapter (which needs
``AnatomicalStructure`` / the canonical body+hand model) feeds it the real model —
that lands with the freemocap env.

See [WS-3 plan](docs/streaming-compatibility/phase-1/03-canonical-frame-extensions.md)
and [09 — Standard Stream Protocol](docs/streaming-compatibility/09-standard-stream-protocol.md).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from freemocap.core.streaming.standard_stream.coordinate_convention import (
    FREEMOCAP_CANONICAL_CONVENTION,
    CoordinateConvention,
)
from freemocap.core.streaming.standard_stream.stream_schema import (
    ChannelGroup,
    ChannelKind,
    RestPose,
    StreamSchema,
)

# Column layouts — SSOT alongside the wire contract.
SKELETON_POINT_COLUMNS = ("x", "y", "z", "reprojection_error")
DERIVED_POINT_COLUMNS = ("x", "y", "z")  # derived points (CoM/xcom) have no per-point reprojection error
ROTATION_COLUMNS = ("w", "x", "y", "z")
OVERLAY_2D_COLUMNS = ("x", "y", "visibility")

DEFAULT_DERIVED_POINTS = ("center_of_mass", "xcom")


def build_stream_schema(
    *,
    stream_id: str,
    stream_name: str,
    landmark_names: Sequence[str],
    segment_names: Sequence[str],
    connections: Sequence[tuple[str, str]] = (),
    joint_hierarchy: Mapping[str, Sequence[str]] | None = None,
    camera_ids: Sequence[str] = (),
    convention: CoordinateConvention = FREEMOCAP_CANONICAL_CONVENTION,
    derived_point_names: Sequence[str] = DEFAULT_DERIVED_POINTS,
    rest_pose: RestPose | None = None,
) -> StreamSchema:
    """Assemble the standard-stream schema for one subject + the given cameras.

    Declares (in order): skeleton ``POINTS`` (with ``reprojection_error``), derived
    ``POINTS`` (``center_of_mass`` / ``xcom``), ``ROTATIONS`` per segment (populated
    by WS-5 — NaN until then), and per-camera ``OVERLAY_2D``. Dimensions (subject,
    cameras) are fixed here at creation; a topology change rebuilds the schema.
    """
    units = convention.units.value
    channels = (
        ChannelGroup(kind=ChannelKind.POINTS, names=tuple(landmark_names), columns=SKELETON_POINT_COLUMNS, units=units),
        ChannelGroup(kind=ChannelKind.POINTS, names=tuple(derived_point_names), columns=DERIVED_POINT_COLUMNS, units=units),
        ChannelGroup(kind=ChannelKind.ROTATIONS, names=tuple(segment_names), columns=ROTATION_COLUMNS, units="quaternion"),
        ChannelGroup(kind=ChannelKind.OVERLAY_2D, names=tuple(landmark_names), columns=OVERLAY_2D_COLUMNS, units="px"),
    )
    hierarchy = {key: tuple(children) for key, children in (joint_hierarchy or {}).items()}
    return StreamSchema(
        stream_id=stream_id,
        stream_name=stream_name,
        coordinate_convention=convention,
        channels=channels,
        connections=tuple((proximal, distal) for proximal, distal in connections),
        joint_hierarchy=hierarchy,
        rest_pose=rest_pose,
        camera_ids=tuple(camera_ids),
    )
