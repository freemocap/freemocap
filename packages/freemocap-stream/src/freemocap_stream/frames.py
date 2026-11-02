"""FreeMoCap's `frame` kind for other applications: cameras, keypoints and images.

A frame is fully self-describing: the coordinate convention, every camera, the
model definitions and this frame's observations ride in every message, so any
frame decodes and renders on its own. These helpers build the parts an
application needs without calibration or 3D models, in exactly the shapes
FreeMoCap's encoder produces, so `@freemocap/client` resolves them unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

from freemocap_stream.messages import encode_message, integer

FRAME_KIND = "frame"
OVERLAY_2D = "OVERLAY_2D"
"""Per-camera 2D keypoints in image pixels, columns ("x", "y", "visibility")."""
BOXES_2D = "BOXES_2D"


def coordinate_convention(
    *,
    units: str = "mm",
    handedness: str = "right",
    up_axis: str = "+z",
    forward_axis: str = "+y",
    rotation_frame: str = "local",
    rotation_form: str = "quaternion",
) -> dict[str, str]:
    """The convention every frame declares; the defaults are FreeMoCap's."""
    return {
        "units": units,
        "handedness": handedness,
        "up_axis": up_axis,
        "forward_axis": forward_axis,
        "rotation_frame": rotation_frame,
        "rotation_form": rotation_form,
    }


def uncalibrated_camera(
    camera_id: str, index: int, image_size: tuple[int, int], *, rotation: str = "none",
) -> dict[str, Any]:
    """A live camera without calibration: its images and 2D overlays stream, with no 3D.

    `image_size` is the (width, height) of the image and its overlay coordinates.
    """
    width, height = image_size
    return {
        "id": camera_id,
        "index": integer(index, "camera index"),
        "rotation": rotation,
        "image_size": [integer(width, "width", minimum=1), integer(height, "height", minimum=1)],
        "intrinsics": None,
        "extrinsics": None,
        "world_position": [0.0, 0.0, 0.0],
        "world_orientation": [],
        "match_kind": "unmatched",
        "calibration_camera_id": None,
    }


def channel_block(
    kind: str,
    columns: Sequence[str],
    values: ArrayLike,
    *,
    names: Sequence[str] | None = None,
    camera_id: str | None = None,
    image_size: tuple[int, int] | None = None,
    sample_status: ArrayLike | None = None,
    status_labels: Sequence[str] | None = None,
) -> dict[str, Any]:
    """One channel: a row per entity and a float32 component per column, packed
    little-endian and row-major. NaN marks a missing value.

    Channels outside a model name their rows (`names`); per-camera overlays name
    their camera and the (width, height) their coordinates refer to.
    """
    rows = np.asarray(values, dtype="<f4")
    if rows.ndim != 2 or rows.shape[1] != len(columns):
        raise ValueError(f"Channel values must have shape (entities, {len(columns)}), not {rows.shape}")
    if names is not None and len(names) != rows.shape[0]:
        raise ValueError(f"{len(names)} names for {rows.shape[0]} rows")
    block: dict[str, Any] = {
        "kind": kind,
        "columns": list(columns),
        "data": np.ascontiguousarray(rows).tobytes(),
    }
    if sample_status is not None:
        status = np.asarray(sample_status)
        if status.shape != (rows.shape[0],):
            raise ValueError("Sample status needs one value per row")
        if status.size and (status.dtype.kind not in 'iu' or np.any(status < 0) or np.any(status > 255)):
            raise ValueError("Sample status values must be integers from 0 to 255")
        block["sample_status"] = status.astype(np.uint8).tobytes()
    if status_labels is not None:
        block["status_labels"] = list(status_labels)
    if camera_id is not None:
        block["camera_id"] = camera_id
    if names is not None:
        block["names"] = list(names)
    if image_size is not None:
        block["image_size"] = [integer(image_size[0], "width", minimum=1),
                               integer(image_size[1], "height", minimum=1)]
    return block


def connection_group(name: str, pairs: Sequence[tuple[str, str]], color: str) -> dict[str, Any]:
    """Named keypoint pairs a client draws as lines, in a '#rrggbb' color."""
    return {"name": name, "pairs": [[first, second] for first, second in pairs], "color": color}


def tracker_observation(
    tracker_id: str,
    channels: Sequence[Mapping[str, Any]],
    *,
    detector_type: str | None = None,
    model_id: str | None = None,
    connection_groups: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """One tracker's observations this frame. Without a model (`model_id` None), the
    tracker's own connection groups tell clients which keypoints to join."""
    observation: dict[str, Any] = {
        "tracker_id": tracker_id,
        "detector_type": detector_type or tracker_id,
        "model_id": model_id,
        "channels": list(channels),
    }
    if connection_groups:
        observation["connection_groups"] = list(connection_groups)
    return observation


def encode_frame_message(
    *,
    frame_number: int,
    timestamp: float,
    cameras: Sequence[Mapping[str, Any]],
    trackers: Sequence[Mapping[str, Any]] = (),
    instances: Sequence[Mapping[str, Any]] = (),
    models: Sequence[Mapping[str, Any]] = (),
    image: bytes | bytearray | memoryview | None = None,
    convention: Mapping[str, str] | None = None,
    model_sequence: int = 0,
) -> bytes:
    """Encode one frame message. Its envelope sequence is the frame number and its
    timestamp the source time, as FreeMoCap's relay sends them; `image` is an image
    payload from `encode_image_payload`."""
    return encode_message(
        FRAME_KIND,
        {
            "frame_number": integer(frame_number, "frame number"),
            "model_sequence": integer(model_sequence, "model sequence"),
            "convention": convention if convention is not None else coordinate_convention(),
            "cameras": list(cameras),
            "models": list(models),
            "instances": list(instances),
            "trackers": list(trackers),
            "image": image,
        },
        timestamp=timestamp,
        sequence=frame_number,
    )
