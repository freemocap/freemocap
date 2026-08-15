"""Shared block-assembly helpers for standard-stream sample composition.

These turn an aggregator output message into the per-block float arrays the
channel producers ship. Kept as a sibling of ``stream_sample`` (not inside the
``producers`` package) so ``stream_sample`` can use them without a package-init
import cycle.
"""
from __future__ import annotations

import numpy as np

# Imported at runtime (not TYPE_CHECKING-only): beartype resolves these
# annotations from the module namespace when the functions are called.
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage  # noqa: TC001 — resolved at runtime by beartype
from skellyforge.skellymodels.standard_human.standard_human_model import StandardHuman  # noqa: TC002 — resolved at runtime by beartype


def assemble_rows(
    *,
    names: tuple[str, ...],
    positions: dict[str, np.ndarray | None],
    columns: tuple[str, ...],
) -> np.ndarray:
    """Build a ``(len(names), len(columns))`` float32 block: each name's position
    (first ``len(columns)`` coords) if present, else a NaN row.

    ``columns`` is the group's per-element column tuple (e.g. ``("x","y","z")``
    for a point group, ``("x","y","z","reprojection_error")`` for KEYPOINTS_3D,
    ``("x","y","visibility")`` for OVERLAY_2D, ``("length_mm",)`` for
    SEGMENT_LENGTHS). A position vector may carry more or fewer values than the
    group declares; the first ``len(columns)`` coords are placed, the remainder
    NaN-filled, and a shorter vector is NaN-padded.
    """
    n_cols = len(columns)
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
    return rows


def camera_2d_detections(
    message: AggregationNodeOutputMessage,
    camera_id: str,
) -> dict[str, np.ndarray]:
    """The per-camera tracker 2D detections (``name -> (x, y, visibility)``).

    Reads the camera's ``skeleton_observation`` body-stage keypoints — the
    detector's raw 2D output for that camera's image. Missing/observable but NaN
    points are skipped (the encoder NaN-fills them). Returns an empty dict when
    there is no skeleton observation for this camera (2D-only mode).
    """
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
    """segment name → origin landmark name (from the standard human model)."""
    return {segment.name: segment.origin_landmark for segment in standard_human.segments}
