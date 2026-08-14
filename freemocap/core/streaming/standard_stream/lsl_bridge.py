"""Thin helpers proving the standard-stream → LSL pass-through parity.

A schema maps to an LSL ``StreamInfo`` channel list, and a sample flattens to one
``push_sample`` vector — **including** overlays. Stream dimensions (subjects,
cameras) are **fixed at stream creation**; a topology change (camera add/remove,
subject count) tears down and rebuilds the stream with a new StreamInfo, so the
flattened vector width is constant for the life of a stream. Nothing is excluded.

See [03 — Transports & Adapters](docs/streaming-compatibility/03-emitters.md) and
[09 — Standard Stream Protocol](docs/streaming-compatibility/09-standard-stream-protocol.md).
"""
from __future__ import annotations

import numpy as np

from freemocap.core.streaming.standard_stream.stream_schema import ChannelKind, StreamSchema
from freemocap.core.streaming.standard_stream.stream_sample import StreamSample  # noqa: TC001 — beartype resolves this in the ``sample_to_flat_vector`` signature at runtime


def schema_to_streaminfo_channels(schema: StreamSchema) -> list[tuple[str, str]]:
    """Flatten channel groups → per-column ``(label, unit)`` for an LSL StreamInfo.

    One channel per (entity name × column), in schema order, across **all** groups.
    OVERLAY_2D is expanded per camera (``schema.camera_ids``) — the camera set is
    fixed at stream creation.
    """
    channels: list[tuple[str, str]] = []
    for group in schema.channels:
        if group.kind == ChannelKind.OVERLAY_2D:
            for camera_id in schema.camera_ids:
                for name in group.names:
                    for column in group.columns:
                        channels.append((f"{camera_id}.{name}.{column}", group.units))
        else:
            for name in group.names:
                for column in group.columns:
                    channels.append((f"{name}.{column}", group.units))
    return channels


def sample_to_flat_vector(sample: StreamSample) -> np.ndarray:
    """Flatten a sample's block data (block order) into one float32 ``push_sample`` vector.

    Includes every block (points, rotations, scalars, per-camera overlays) — nothing
    excluded; the stream's dimensions are fixed at creation.
    """
    rows = [np.ascontiguousarray(block.data, dtype=np.float32).reshape(-1) for block in sample.blocks]
    if not rows:
        return np.empty(0, dtype=np.float32)
    return np.concatenate(rows)
