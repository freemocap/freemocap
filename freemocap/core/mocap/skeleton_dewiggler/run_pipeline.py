"""
Run the skeleton filter pipeline on a (frames, keypoints, 3) numpy array.

Expects:
    skeleton_fr_name_xyz: np.ndarray with shape (frame_count, keypoint_count, 3)
    marker_names: list[str] with length keypoint_count

Produces:
    filtered_fr_name_xyz: np.ndarray with same shape, filtered + bone-constrained
"""

import numpy as np

from bone_length_estimator import AnthropometricPrior, BoneLengthEstimator, EstimatorConfig
from mediapipe_skeleton_config import SkeletonDefinition
from skeleton_filter_pipeline import FilterConfig, SkeletonFilterPipeline


def run_pipeline(
    *,
    skeleton_fr_name_xyz: np.ndarray,
    marker_names: list[str],
    skeleton: SkeletonDefinition,
    prior: AnthropometricPrior,
    height_meters: float,
    noise_sigma: float = 0.008,
    fps: float = 30.0,
    filter_config: FilterConfig = FilterConfig(),
    estimator_config: EstimatorConfig = EstimatorConfig(),
    calibration_frame_count: int = 100,
) -> np.ndarray:
    """
    Run One Euro → FABRIK pipeline on a skeleton array.

    Args:
        skeleton_fr_name_xyz: (frame_count, keypoint_count, 3) raw positions.
        marker_names: keypoint names, length must match axis 1.
        skeleton: skeleton topology definition.
        prior: anthropometric prior for bone length estimation.
        height_meters: subject standing height in meters.
        noise_sigma: per-keypoint position noise std in meters.
        fps: frame rate in Hz (used to generate timestamps).
        filter_config: One Euro + FABRIK tuning parameters.
        estimator_config: bone length estimator parameters.
        calibration_frame_count: how many initial frames to use for
                                 bone length estimation before starting
                                 the filter pipeline.

    Returns:
        (frame_count, keypoint_count, 3) filtered + constrained positions.
    """
    frame_count, keypoint_count, n_dims = skeleton_fr_name_xyz.shape
    if n_dims != 3:
        raise ValueError(f"Expected 3 dimensions, got {n_dims}")
    if len(marker_names) != keypoint_count:
        raise ValueError(
            f"marker_names length ({len(marker_names)}) != "
            f"keypoint axis size ({keypoint_count})"
        )
    if calibration_frame_count > frame_count:
        raise ValueError(
            f"calibration_frame_count ({calibration_frame_count}) > "
            f"frame_count ({frame_count})"
        )
    if fps <= 0.0:
        raise ValueError(f"fps must be positive, got {fps}")

    name_to_idx: dict[str, int] = {name: i for i, name in enumerate(marker_names)}

    def frame_to_dict(frame_idx: int) -> dict[str, np.ndarray]:
        return {
            name: skeleton_fr_name_xyz[frame_idx, idx].copy()
            for name, idx in name_to_idx.items()
        }

    # --- Phase 1: Estimate bone lengths from initial frames ---
    estimator = BoneLengthEstimator.create(
        skeleton=skeleton,
        prior=prior,
        height_meters=height_meters,
        noise_sigma=noise_sigma,
        config=estimator_config,
    )

    for i in range(calibration_frame_count):
        estimator.observe(positions=frame_to_dict(i))

    bone_lengths = estimator.current_lengths
    print(f"Bone lengths estimated from {calibration_frame_count} calibration frames:")
    for bone_key, length in sorted(bone_lengths.items()):
        est = estimator.get_estimate(bone_key=bone_key)
        print(f"  {bone_key:45s} = {length*100:6.2f} cm  (confidence={est.confidence:.2f})")

    # --- Phase 2: Build pipeline ---
    pipeline = SkeletonFilterPipeline.from_bone_lengths(
        skeleton=skeleton,
        config=filter_config,
        bone_lengths=bone_lengths,
    )

    # --- Phase 3: Process all frames ---
    output = np.empty_like(skeleton_fr_name_xyz)

    for i in range(frame_count):
        t = (i + 1) / fps
        positions = frame_to_dict(i)
        filtered = pipeline.process_frame(t=t, positions=positions)

        # Also keep feeding the estimator (it keeps refining)
        estimator.observe(positions=positions)

        for name, idx in name_to_idx.items():
            if name in filtered:
                output[i, idx] = filtered[name]
            else:
                output[i, idx] = skeleton_fr_name_xyz[i, idx]

    print(f"Processed {frame_count} frames")
    return output


# ============================================================
# Example usage
# ============================================================

if __name__ == "__main__":
    # --- Synthetic test data ---
    np.random.seed(42)

    skeleton = SkeletonDefinition.mediapipe_body()
    prior = AnthropometricPrior.mediapipe_body()

    marker_names = [
        "left_shoulder", "right_shoulder", "left_hip", "right_hip",
        "left_elbow", "right_elbow", "left_wrist", "right_wrist",
        "left_knee", "right_knee", "left_ankle", "right_ankle",
        "left_heel", "right_heel", "left_foot_index", "right_foot_index",
        "nose", "left_eye_inner", "left_eye", "left_eye_outer", "left_ear",
        "right_eye_inner", "right_eye", "right_eye_outer", "right_ear",
        "mouth_left", "mouth_right",
        "left_pinky", "left_index", "left_thumb",
        "right_pinky", "right_index", "right_thumb",
    ]

    frame_count = 300
    keypoint_count = len(marker_names)

    # Ground truth positions for a 1.70m person
    true_positions = {
        "left_shoulder": [-0.18, 0, 1.42], "right_shoulder": [0.18, 0, 1.42],
        "left_hip": [-0.09, 0, 0.95], "right_hip": [0.09, 0, 0.95],
        "left_elbow": [-0.38, 0, 1.22], "right_elbow": [0.38, 0, 1.22],
        "left_wrist": [-0.50, 0, 1.05], "right_wrist": [0.50, 0, 1.05],
        "left_knee": [-0.09, 0, 0.53], "right_knee": [0.09, 0, 0.53],
        "left_ankle": [-0.09, 0, 0.04], "right_ankle": [0.09, 0, 0.04],
        "left_heel": [-0.09, -0.04, 0.0], "right_heel": [0.09, -0.04, 0.0],
        "left_foot_index": [-0.09, 0.12, 0.0], "right_foot_index": [0.09, 0.12, 0.0],
        "nose": [0, 0, 1.68],
        "left_eye_inner": [-0.02, 0, 1.70], "left_eye": [-0.03, 0, 1.70],
        "left_eye_outer": [-0.04, 0, 1.70], "left_ear": [-0.07, 0, 1.69],
        "right_eye_inner": [0.02, 0, 1.70], "right_eye": [0.03, 0, 1.70],
        "right_eye_outer": [0.04, 0, 1.70], "right_ear": [0.07, 0, 1.69],
        "mouth_left": [-0.02, 0, 1.65], "mouth_right": [0.02, 0, 1.65],
        "left_pinky": [-0.52, 0, 1.03], "left_index": [-0.51, 0, 1.02],
        "left_thumb": [-0.49, 0.02, 1.04],
        "right_pinky": [0.52, 0, 1.03], "right_index": [0.51, 0, 1.02],
        "right_thumb": [0.49, 0.02, 1.04],
    }

    # Build noisy array
    name_to_idx = {name: i for i, name in enumerate(marker_names)}
    skeleton_fr_name_xyz = np.zeros((frame_count, keypoint_count, 3))
    for frame in range(frame_count):
        for name, idx in name_to_idx.items():
            base = np.array(true_positions.get(name, [0, 0, 0]), dtype=np.float64)
            skeleton_fr_name_xyz[frame, idx] = base + np.random.normal(scale=0.01, size=3)

    # Run
    filtered = run_pipeline(
        skeleton_fr_name_xyz=skeleton_fr_name_xyz,
        marker_names=marker_names,
        skeleton=skeleton,
        prior=prior,
        height_meters=1.75,  # slightly wrong guess
        noise_sigma=0.008,
        fps=30.0,
        calibration_frame_count=100,
    )

    # Verify output shape
    assert filtered.shape == skeleton_fr_name_xyz.shape
    print(f"\nOutput shape: {filtered.shape}")

    # Compare noise levels: std of frame-to-frame jitter
    raw_jitter = np.mean(np.std(np.diff(skeleton_fr_name_xyz, axis=0), axis=0))
    filtered_jitter = np.mean(np.std(np.diff(filtered, axis=0), axis=0))
    print(f"Mean frame-to-frame jitter std: raw={raw_jitter*1000:.2f}mm → filtered={filtered_jitter*1000:.2f}mm")
    print(f"Jitter reduction: {(1 - filtered_jitter/raw_jitter)*100:.0f}%")