"""E2E: posthoc mocap pipeline produces 3D output using the session calibration."""
import logging

import numpy as np
import pytest

from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig

from freemocap.tests.pipelines.helpers import find_body_3d_npy, wait_for_pipeline

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
