"""Adapters that turn each pipeline's output into a canonical-named position
time series for the segment-length diagnostics in
``freemocap.core.kinematics.segment_lengths``.

For the limb segments we validate (upper arm, forearm, thigh, shank), the joint
landmark names are identical COCO names across mediapipe (posthoc) and RTMPose
(realtime) and the canonical model — so no tracker→canonical remap is needed;
each adapter just collects ``{landmark_name: (n_frames, 3)}``.
"""
from __future__ import annotations

from pathlib import Path  # noqa: TC003

import numpy as np

from freemocap.core.kinematics.segment_lengths import find_body_csv, load_body_positions_from_csv


def load_posthoc_body_positions(output_dir: Path) -> dict[str, np.ndarray]:
    """Load the posthoc body 3D trajectories as ``{landmark_name: (n_frames, 3)}``.

    Thin wrapper over the core ``find_body_csv``/``load_body_positions_from_csv``.
    The CSV is named after the tracking model (e.g. ``charuco_board_5_3_body_3d_xyz.csv``),
    not a fixed ``mediapipe_body_3d_xyz.csv``, so resolution is delegated to
    ``find_body_csv`` rather than hardcoding a filename here.
    """
    csv_path = find_body_csv(output_dir)
    return load_body_positions_from_csv(csv_path)


def positions_from_aggregation_outputs(
    outputs: list,
    *,
    field: str = "keypoints_arrays",
) -> dict[str, np.ndarray]:
    """Collect a position time series from realtime AggregationNodeOutputMessages.

    Parameters
    ----------
    outputs
        Ordered list of ``AggregationNodeOutputMessage`` (one per processed frame).
    field
        Which named-point dict to read: ``"keypoints_arrays"`` (raw triangulated,
        the honest reconstruction — default) or ``"skeleton"`` (the rigidified
        canonical skeleton; its bone lengths are the enforced rigid estimates, so
        use it to check rigidity + posthoc equivalence, not as an independent
        measure of the raw reconstruction).

    Returns ``{landmark_name: (n_frames, 3)}``, NaN where a point was absent.
    """
    n_frames = len(outputs)
    positions: dict[str, np.ndarray] = {}
    for frame_idx, message in enumerate(outputs):
        points = getattr(message, field, None) or {}
        for name, pos in points.items():
            if name not in positions:
                positions[name] = np.full((n_frames, 3), np.nan)
            positions[name][frame_idx] = np.asarray(pos, dtype=float).reshape(3)
    return positions
