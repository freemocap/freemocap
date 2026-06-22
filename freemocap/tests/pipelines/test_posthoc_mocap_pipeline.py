"""E2E: posthoc mocap pipeline produces 3D output using the session calibration.

Blender export is disabled so the test doesn't shell out to / open Blender.
"""
import numpy as np
import pytest

from freemocap.core.tasks.calibration.calibration_task_config import CalibrationSource
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig

from freemocap.tests.pipelines.helpers import find_body_3d_npy, wait_for_pipeline


def _run_mocap(posthoc_manager, recording_info, mocap_config) -> None:
    pipeline = posthoc_manager.create_mocap_pipeline(
        recording_info=recording_info,
        mocap_config=mocap_config,
    )
    wait_for_pipeline(pipeline)


@pytest.mark.e2e
def test_posthoc_mocap_most_recent_calibration_produces_3d(posthoc_mocap_output_dir):
    # posthoc_mocap_output_dir fixture runs mocap once (most-recent calibration).
    output_dir = posthoc_mocap_output_dir
    assert output_dir.exists(), f"output_data/ not found at {output_dir}"
    npy_files = list(output_dir.glob("*.npy"))
    csv_files = list(output_dir.glob("*.csv"))
    assert npy_files, f"No .npy files in {output_dir}"
    assert csv_files, f"No .csv files in {output_dir}"

    data = np.load(find_body_3d_npy(npy_files))
    assert data.ndim >= 2, f"Expected >=2D body array, got shape {data.shape}"
    assert not np.all(np.isnan(data)), "Body 3D data is all-NaN — triangulation failed"


@pytest.mark.e2e
def test_posthoc_mocap_specified_calibration_path(
    test_recording_path, recording_info, posthoc_manager, calibration_toml_path
):
    _run_mocap(
        posthoc_manager,
        recording_info,
        PosthocMocapPipelineConfig(
            calibration_source=CalibrationSource.SPECIFIED,
            calibration_toml_path=str(calibration_toml_path),
            export_to_blender=False,
            auto_open_blend_file=False,
        ),
    )
    output_dir = test_recording_path / "output_data"
    assert list(output_dir.glob("*.npy")), "No .npy output for specified-calibration run"
