"""Adapters that turn each pipeline's output into a canonical-named position
time series for the segment-length diagnostics in
``freemocap.core.kinematics.segment_lengths``.

For the limb segments we validate (upper arm, forearm, thigh, shank), the joint
landmark names are identical COCO names across mediapipe (posthoc) and RTMPose
(realtime) and the canonical model — so no tracker→canonical remap is needed;
each adapter just collects ``{landmark_name: (n_frames, 3)}``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Posthoc body 3D CSV is long-format: frame, keypoint, x, y, z
_POSTHOC_BODY_CSV = "mediapipe_body_3d_xyz.csv"


def load_posthoc_body_positions(output_dir: Path) -> dict[str, np.ndarray]:
    """Load the posthoc body 3D trajectories as ``{landmark_name: (n_frames, 3)}``.

    Reads the long-format ``mediapipe_body_3d_xyz.csv`` written by the posthoc
    mocap pipeline. Keypoint names are used verbatim (already canonical for the
    limb joints we measure).
    """
    csv_path = Path(output_dir) / _POSTHOC_BODY_CSV
    if not csv_path.exists():
        raise FileNotFoundError(f"Posthoc body CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    expected = {"frame", "keypoint", "x", "y", "z"}
    if not expected.issubset(df.columns):
        raise ValueError(
            f"{csv_path} missing columns {expected - set(df.columns)} "
            f"(has {list(df.columns)})"
        )

    frames = np.sort(df["frame"].unique())
    n_frames = len(frames)
    frame_to_idx = {int(f): i for i, f in enumerate(frames)}

    positions: dict[str, np.ndarray] = {}
    for keypoint, group in df.groupby("keypoint"):
        arr = np.full((n_frames, 3), np.nan)
        idx = group["frame"].map(frame_to_idx).to_numpy()
        arr[idx, 0] = group["x"].to_numpy()
        arr[idx, 1] = group["y"].to_numpy()
        arr[idx, 2] = group["z"].to_numpy()
        positions[str(keypoint)] = arr
    return positions


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
        the honest reconstruction — default) or ``"skeleton"`` (FABRIK-fitted,
        canonical names; note its bone lengths are clamped to the prior so it is
        not an independent anthropometry test).

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
