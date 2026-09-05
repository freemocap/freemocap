"""E2E: posthoc mocap pipeline produces 3D output using the session calibration."""
import csv
import logging
from collections import defaultdict

import numpy as np
import pytest

from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig

from freemocap.tests.pipelines.helpers import find_body_3d_npy, wait_for_pipeline
from freemocap.tests.pipelines.real_data_numeric_bounds import (
    BILATERAL_LENGTH_TOLERANCE,
    COM_Z_MAX_MM,
    COM_Z_MIN_MM,
    EXPECTED_BODY_LANDMARK_COUNT,
    EXPECTED_FRAME_COUNT,
    FEMUR_LENGTH_MM_RANGE,
    FOREARM_LENGTH_MM_RANGE,
    MIN_FINITE_FRACTION,
    SHANK_LENGTH_MM_RANGE,
    UPPER_ARM_LENGTH_MM_RANGE,
)

logger = logging.getLogger(__name__)


def _run_mocap(posthoc_manager, recording_info, mocap_config) -> None:
    logger.info(
        f"Launching mocap pipeline: recording={recording_info.recording_name!r}  "
        f"calibration_toml_path={mocap_config.calibration_toml_path}"
    )
    pipeline = posthoc_manager.create_mocap_pipeline(
        recording_info=recording_info,
        mocap_config=mocap_config,
    )
    logger.info(f"Mocap pipeline created: id={pipeline.id}")
    wait_for_pipeline(pipeline)


@pytest.mark.e2e
def test_posthoc_mocap_most_recent_calibration_produces_3d(posthoc_mocap_output_dir):
    output_dir = posthoc_mocap_output_dir
    logger.info(f"Checking output_data: {output_dir}")
    assert output_dir.exists(), f"output_data/ not found at {output_dir}"

    npy_files = list(output_dir.glob("*.npy"))
    csv_files = list(output_dir.glob("*.csv"))
    logger.info(f"Found {len(npy_files)} .npy files and {len(csv_files)} .csv files")
    for f in sorted(npy_files + csv_files):
        logger.info(f"  {f.name}  ({f.stat().st_size / 1024:.1f} KB)")

    assert npy_files, f"No .npy files in {output_dir}"
    assert csv_files, f"No .csv files in {output_dir}"

    body_npy = find_body_3d_npy(npy_files)
    logger.info(f"Loading body 3D array from: {body_npy.name}")
    data = np.load(body_npy)
    logger.info(f"Body 3D array shape: {data.shape}  dtype={data.dtype}")

    nan_frac = float(np.isnan(data).mean())
    finite_frac = 1.0 - nan_frac
    logger.info(f"NaN fraction: {nan_frac:.1%}  |  Finite fraction: {finite_frac:.1%}")

    assert data.ndim >= 2, f"Expected >=2D body array, got shape {data.shape}"
    assert not np.all(np.isnan(data)), "Body 3D data is all-NaN — triangulation failed"
    logger.info("Body 3D data exists and has finite values — PASS")


@pytest.mark.e2e
def test_posthoc_mocap_specified_calibration_path(
    test_recording_path, recording_info, posthoc_manager, calibration_toml_path
):
    logger.info(
        f"Testing SPECIFIED calibration source: toml={calibration_toml_path.name}"
    )
    _run_mocap(
        posthoc_manager,
        recording_info,
        PosthocMocapPipelineConfig(
            calibration_toml_path=str(calibration_toml_path),
            export_to_blender=False,
            auto_open_blend_file=False,
        ),
    )
    output_dir = test_recording_path / "output_data"
    npy_files = list(output_dir.glob("*.npy"))
    logger.info(f"output_data has {len(npy_files)} .npy files after specified-calibration run")
    assert npy_files, "No .npy output for specified-calibration run"
    logger.info("Specified-calibration mocap produced .npy output — PASS")


def _body_landmark_trajectories(output_dir) -> dict[str, np.ndarray]:
    """Body landmark trajectories keyed by name, read from the tidy body CSV."""
    trajectories = defaultdict(list)
    csv_path = output_dir / "rtmpose_body_3d_xyz.csv"
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            trajectories[row["keypoint"]].append(
                (float(row["x"]), float(row["y"]), float(row["z"]))
            )
    return {name: np.asarray(points) for name, points in trajectories.items()}


def _median_distance_mm(trajectories: dict[str, np.ndarray], a: str, b: str) -> float:
    distances = np.linalg.norm(trajectories[a] - trajectories[b], axis=1)
    distances = distances[np.isfinite(distances)]
    return float(np.median(distances))


@pytest.mark.e2e
def test_reconstructed_anatomy_is_numerically_sane(posthoc_mocap_output_dir):
    """Structural + numerical correctness of the reconstruction on real data.

    No semantic reading of the movement (no A-pose / balance / jump detection) — only the
    things that must be true of any correct body: the right array shape, finite coverage, a
    centre of mass that stays above the floor, and anatomically plausible, bilaterally
    symmetric bone lengths.
    """
    output_dir = posthoc_mocap_output_dir
    # The 27-landmark RTMPose body specifically (not the rigid variant or the charuco board).
    body = np.load(output_dir / "rtmpose_body_3d_xyz.npy")
    assert body.shape == (EXPECTED_FRAME_COUNT, EXPECTED_BODY_LANDMARK_COUNT, 3), (
        f"body 3D shape {body.shape}, expected "
        f"({EXPECTED_FRAME_COUNT}, {EXPECTED_BODY_LANDMARK_COUNT}, 3)"
    )
    finite_fraction = float(np.isfinite(body).mean())
    assert finite_fraction >= MIN_FINITE_FRACTION, (
        f"only {finite_fraction:.1%} finite values (expected >= {MIN_FINITE_FRACTION:.1%})"
    )

    com = np.load(output_dir / "rtmpose_body_total_body_center_of_mass.npy").reshape(-1, 3)
    com_z = com[:, 2]
    assert com_z.min() >= COM_Z_MIN_MM, f"CoM dropped to {com_z.min():.0f} mm (floor {COM_Z_MIN_MM})"
    assert com_z.max() <= COM_Z_MAX_MM, f"CoM rose to {com_z.max():.0f} mm (ceiling {COM_Z_MAX_MM})"

    trajectories = _body_landmark_trajectories(output_dir)
    for a, b, label, (lo, hi) in [
        ("left_hip_socket", "left_knee", "femur", FEMUR_LENGTH_MM_RANGE),
        ("left_knee", "left_ankle", "shank", SHANK_LENGTH_MM_RANGE),
        ("left_acromion", "left_elbow", "upper arm", UPPER_ARM_LENGTH_MM_RANGE),
        ("left_elbow", "left_wrist", "forearm", FOREARM_LENGTH_MM_RANGE),
    ]:
        length = _median_distance_mm(trajectories, a, b)
        assert lo < length < hi, f"{label} {length:.0f} mm outside {lo}-{hi} mm"
        right_length = _median_distance_mm(
            trajectories, a.replace("left_", "right_"), b.replace("left_", "right_")
        )
        asymmetry = abs(length - right_length) / length
        assert asymmetry <= BILATERAL_LENGTH_TOLERANCE, (
            f"{label} left/right differ by {asymmetry:.1%} "
            f"({length:.0f} vs {right_length:.0f} mm)"
        )
    logger.info("Reconstructed anatomy numerically sane — PASS")
