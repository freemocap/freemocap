"""Calibration selection is explicit and cannot retain unreadable geometry."""

from pathlib import Path

import pytest
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.mocap.posthoc_mocap_task import run_posthoc_mocap_task
from freemocap.tests.calibration.test_calibration_state_latch import build_loaded_tracker


def test_clear_does_not_load_another_calibration(tmp_path: Path) -> None:
    source = build_loaded_tracker().calibration
    assert source is not None
    path = tmp_path / 'selected.toml'
    source.dump_anipose_toml(path=path)
    tracker = CalibrationStateTracker.create_and_try_load(calibration_toml_path=path)
    assert tracker.is_valid
    assert tracker.set_source_path(calibration_toml_path=None)
    assert not tracker.is_valid
    assert tracker.calibration_path is None
    assert not tracker.check_for_update()
    assert not CalibrationStateTracker.create_and_try_load(calibration_toml_path=None).is_valid


def test_unreadable_selection_does_not_retain_previous_geometry(tmp_path: Path) -> None:
    source = build_loaded_tracker().calibration
    assert source is not None
    path = tmp_path / 'selected.toml'
    source.dump_anipose_toml(path=path)
    tracker = CalibrationStateTracker.create_and_try_load(calibration_toml_path=path)
    with pytest.raises(FileNotFoundError):
        tracker.set_source_path(calibration_toml_path=tmp_path / 'missing.toml')
    assert not tracker.is_valid
    assert tracker.calibration is None
    assert tracker.set_source_path(calibration_toml_path=path)
    path.unlink()
    with pytest.raises(FileNotFoundError):
        tracker.check_for_update()
    assert not tracker.is_valid


def test_multicamera_processing_requires_explicit_calibration(tmp_path: Path) -> None:
    recording = RecordingInfo(recording_directory=str(tmp_path), recording_name='recording', mic_device_index=-1)
    metadata = {camera_id: VideoMetadata(
        file_path=tmp_path / f'{camera_id}.mp4', width=1280, height=720,
        fps=30.0, frame_count=1, fourcc='mp4v', duration_seconds=1 / 30, end_frame=1,
    ) for camera_id in ('cam0', 'cam1')}
    with pytest.raises(ValueError, match='explicitly selected calibration'):
        run_posthoc_mocap_task(
            frame_observations=[], recording_info=recording, video_metadata=metadata,
            task_config=PosthocMocapPipelineConfig(calibration_toml_path=None), selected_board=None,
        )
