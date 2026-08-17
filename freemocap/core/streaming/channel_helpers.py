"""Shared channel-assembly helpers for frame-channel composition.

Turn an aggregator output message into the packed float32 bytes a ChannelBlock
ships. Kept as a leaf (not inside the producers package) so no package-init
import cycle.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from skellyforge.skellymodels.standard_human.standard_human_model import StandardHuman  # noqa: TC002


def assemble_channel_bytes(
    *,
    names: tuple[str, ...],
    positions: dict[str, np.ndarray | None],
    n_cols: int,
) -> bytes:
    """Pack (len(names), n_cols) float32 little-endian bytes, NaN-filling
    missing names (a missing point is a NaN row, never a dropped row)."""
    rows = np.full((len(names), n_cols), np.nan, dtype=np.float32)
    for i, name in enumerate(names):
        pos = positions.get(name)
        if pos is None:
            continue
        arr = np.asarray(pos, dtype=np.float32)
        if arr.size == 0:
            continue
        k = min(n_cols, int(arr.size))
        rows[i, :k] = arr[:k]
    return rows.tobytes(order="C")


def camera_2d_detections(
    message: Any,  # duck-typed: the concrete type pulls skellytracker/mediapipe
    camera_id: str,
) -> dict[str, np.ndarray]:
    """The per-camera tracker 2D detections (name -> (x, y, visibility))."""
    cam_output = message.camera_node_outputs.get(camera_id)
    if cam_output is None or cam_output.skeleton_observation is None:
        return {}
    observation = cam_output.skeleton_observation
    body_stage = observation.stages.get("body")
    if body_stage is None or body_stage.keypoints is None:
        return {}
    kpts = body_stage.keypoints
    detections: dict[str, np.ndarray] = {}
    for i, name in enumerate(kpts.names):
        x, y, _z = kpts.xyz[i]
        if np.isnan(x) or np.isnan(y):
            continue
        detections[name] = np.array([x, y, kpts.visibility[i]], dtype=np.float32)
    return detections


def origin_landmark_names(standard_human: StandardHuman) -> dict[str, str]:
    """segment name -> origin landmark name (from the standard human model)."""
    return {segment.name: segment.origin_landmark for segment in standard_human.segments}
