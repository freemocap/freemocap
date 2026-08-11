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

import msgspec

from freemocap.core.streaming.standard_stream.coordinate_convention import CoordinateConvention


class ChannelKind(enum.IntEnum):
    """The kinds of channel group (and block). Wire value = the block_kind byte."""

    POINTS = 0      # 3D points — skeleton landmarks + derived points (center_of_mass, xcom).
                    # columns e.g. (x, y, z, reprojection_error); a group may omit the error column.
    ROTATIONS = 1   # per-segment quaternion — columns (w, x, y, z), w-first (bs/ convention)
    OVERLAY_2D = 2  # per-camera 2D projection — columns (x, y, visibility); one block per camera


class ChannelGroup(msgspec.Struct, frozen=True):
    """One ordered group of channels: which entities, which columns, what units."""

    kind: ChannelKind
    names: tuple[str, ...]    # canonical landmark / segment names
    columns: tuple[str, ...]  # per-element columns, e.g. ("x", "y", "z", "reprojection_error")
    units: str


class RestPose(msgspec.Struct, frozen=True):
    """The declared T-pose: identity rotation == this pose.

    Populated by the canonical human model (WS-3 / WS-5). Empty in the WS-1
    contract. Orientations are wxyz quaternions.
    """

    positions: dict[str, tuple[float, float, float]] = msgspec.field(default_factory=dict)
    reference_orientations: dict[str, tuple[float, float, float, float]] = msgspec.field(default_factory=dict)


class StreamSchema(msgspec.Struct):
    """The full static descriptor for one standard stream (one subject's layout)."""

    stream_id: str    # unique (uuid-derived) — the key everything is addressed by
    stream_name: str  # human-facing label; not required to be unique
    coordinate_convention: CoordinateConvention
    channels: tuple[ChannelGroup, ...]
    connections: tuple[tuple[str, str], ...] = ()
    joint_hierarchy: dict[str, tuple[str, ...]] = msgspec.field(default_factory=dict)
    rest_pose: RestPose | None = None
    message_type: str = "stream_schema"


_ENCODER = msgspec.json.Encoder()


def encode_schema(schema: StreamSchema) -> bytes:
    """Serialize a schema to JSON bytes (sent once on connect / on change)."""
    return _ENCODER.encode(schema)


def decode_schema(data: bytes) -> StreamSchema:
    """Reconstruct a schema from JSON bytes."""
    return msgspec.json.decode(data, type=StreamSchema)
