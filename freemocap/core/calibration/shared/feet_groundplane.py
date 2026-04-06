"""Estimate ground plane from person's foot marker positions.

Ported from skellyforge's Human.put_skeleton_on_ground() method.
Returns a GroundPlaneResult that can be applied to camera extrinsics
via apply_groundplane_to_cameras().
"""

import logging

import numpy as np
from numpy.typing import NDArray

from freemocap.core.calibration.shared.groundplane_alignment import GroundPlaneResult

logger = logging.getLogger(__name__)

REQUIRED_FOOT_MARKERS = [
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
]

UP_DIRECTION_MARKERS = [
    "left_shoulder",
    "right_shoulder",
]


def _find_still_frame(trajectories: NDArray[np.float64]) -> int:
    """Find frame where foot markers are most stationary.

    Args:
        trajectories: (n_frames, n_markers, 3) foot marker positions.

    Returns:
        Frame index with minimum maximum velocity across markers.
    """
    velocity = np.linalg.norm(np.diff(trajectories, axis=0), axis=2)
    visible_frames = ~np.isnan(velocity).any(axis=1)

    if not visible_frames.any():
        raise ValueError("No frames with all foot markers visible")

    max_velocity_per_frame = np.nanmax(velocity[visible_frames], axis=1)
    lowest_velocity_idx = int(np.nanargmin(max_velocity_per_frame))
    return int(np.where(visible_frames)[0][lowest_velocity_idx])


def _get_unit_vector(vector: NDArray[np.float64]) -> NDArray[np.float64]:
    norm = np.linalg.norm(vector)
    if norm < 1e-10:
        raise ValueError("Cannot normalize near-zero vector")
    return vector / norm


def estimate_groundplane_from_feet(
    skeleton_3d: NDArray[np.float64],
    marker_name_to_index: dict[str, int],
) -> GroundPlaneResult | None:
    """Estimate ground plane from foot marker positions.

    Uses the skellyforge approach: find still frame, compute basis vectors
    from foot positions and shoulder midpoint (neck_center proxy).

    Args:
        skeleton_3d: (n_frames, n_markers, 3) triangulated skeleton data.
        marker_name_to_index: Mapping of marker names to indices in the
            skeleton_3d array. Must contain left_heel, right_heel,
            left_foot_index, right_foot_index, left_shoulder, right_shoulder.

    Returns:
        GroundPlaneResult, or None if required markers are missing.
    """
    # Validate required markers
    all_required = REQUIRED_FOOT_MARKERS + UP_DIRECTION_MARKERS
    missing = [m for m in all_required if m not in marker_name_to_index]
    if missing:
        logger.warning(f"Missing markers for feet ground plane: {missing}")
        return None

    # Extract foot trajectories: (n_frames, 4, 3)
    foot_indices = [marker_name_to_index[m] for m in REQUIRED_FOOT_MARKERS]
    foot_trajectories = skeleton_3d[:, foot_indices, :]

    # Find still frame
    try:
        still_frame = _find_still_frame(foot_trajectories)
    except ValueError as e:
        logger.warning(f"Could not find still frame for feet ground plane: {e}")
        return None

    logger.info(f"Using frame {still_frame} for feet ground plane estimation")

    # Center = mean of 4 foot markers at still frame
    center = np.mean(foot_trajectories[still_frame], axis=0)
    if np.isnan(center).any():
        logger.warning("Foot marker center contains NaN at still frame")
        return None

    # Forward direction: center → midpoint of foot_index markers
    left_foot_index_pos = skeleton_3d[still_frame, marker_name_to_index["left_foot_index"]]
    right_foot_index_pos = skeleton_3d[still_frame, marker_name_to_index["right_foot_index"]]
    mid_foot_index = (left_foot_index_pos + right_foot_index_pos) / 2

    # Up direction: center → neck_center (midpoint of shoulders)
    left_shoulder = skeleton_3d[still_frame, marker_name_to_index["left_shoulder"]]
    right_shoulder = skeleton_3d[still_frame, marker_name_to_index["right_shoulder"]]
    neck_center = (left_shoulder + right_shoulder) / 2

    try:
        forward = _get_unit_vector(mid_foot_index - center)
        up = _get_unit_vector(neck_center - center)

        x_hat = _get_unit_vector(np.cross(forward, up))
        y_hat = _get_unit_vector(np.cross(up, x_hat))
        z_hat = _get_unit_vector(np.cross(x_hat, y_hat))
    except ValueError as e:
        logger.warning(f"Could not compute basis vectors for feet ground plane: {e}")
        return None

    rotation_matrix = np.column_stack([x_hat, y_hat, z_hat])

    return GroundPlaneResult(
        origin=center,
        rotation_matrix=rotation_matrix,
        method="feet",
    )


def build_mediapipe_body_marker_name_to_index() -> dict[str, int]:
    """Build marker name → index mapping for mediapipe body landmarks.

    The body landmarks are the first 33 markers in the mediapipe skeleton
    array, in the order defined by mediapipe_model_info.yaml.
    """
    names = [
        "nose", "left_eye_inner", "left_eye", "left_eye_outer",
        "right_eye_inner", "right_eye", "right_eye_outer",
        "left_ear", "right_ear", "mouth_left", "mouth_right",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_pinky", "right_pinky",
        "left_index", "right_index", "left_thumb", "right_thumb",
        "left_hip", "right_hip", "left_knee", "right_knee",
        "left_ankle", "right_ankle", "left_heel", "right_heel",
        "left_foot_index", "right_foot_index",
    ]
    return {name: idx for idx, name in enumerate(names)}
