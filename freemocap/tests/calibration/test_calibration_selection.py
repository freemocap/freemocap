"""Null selects the latest calibration; explicit paths cannot silently fall back."""

from pathlib import Path
import os
import numpy as np
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.keypoints import Keypoints

import pytest
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.core.tasks.calibration.shared import calibration_paths
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.mocap.posthoc_mocap_task import run_posthoc_mocap_task
from freemocap.tests.calibration.test_calibration_state_latch import build_loaded_tracker


def test_null_loads_latest_and_switching_back_restores_default(tmp_path: Path, monkeypatch) -> None:
    source = build_loaded_tracker().calibration
    assert source is not None
    path = tmp_path / 'selected.toml'
    source.save_toml(path=path)
    latest = tmp_path / 'last_successful_camera_calibration.toml'
    source.save_toml(path=latest)
    monkeypatch.setattr(calibration_paths, 'get_last_successful_calibration_toml_path', lambda: latest)
    tracker = CalibrationStateTracker.create_and_try_load(calibration_toml_path=path)
    assert tracker.is_valid
    assert tracker.set_source_path(calibration_toml_path=None)
    assert tracker.is_valid
    assert tracker.calibration_path == latest
    assert not tracker.check_for_update()
    default_tracker = CalibrationStateTracker.create_and_try_load(calibration_toml_path=None)
    assert default_tracker.is_valid
    assert default_tracker.calibration_path == latest
    updated = source.model_copy(update={'board': source.board.model_copy(update={'square_length_mm': 58.0})})
    previous_mtime = latest.stat().st_mtime
    updated.save_toml(path=latest)
    os.utime(latest, (previous_mtime + 2, previous_mtime + 2))
    assert default_tracker.check_for_update()
    assert default_tracker.calibration.board.square_length_mm == 58.0
    assert not default_tracker.check_for_update()


def test_missing_default_is_loaded_when_first_calibration_is_saved(tmp_path: Path, monkeypatch) -> None:
    latest = tmp_path / 'last_successful_camera_calibration.toml'
    monkeypatch.setattr(calibration_paths, 'get_last_successful_calibration_toml_path', lambda: latest)
    tracker = CalibrationStateTracker.create_and_try_load(calibration_toml_path=None)
    assert not tracker.is_valid
    assert not tracker.check_for_update()
    source = build_loaded_tracker().calibration
    assert source is not None
    source.save_toml(path=latest)
    assert tracker.check_for_update()
    assert tracker.is_valid
    assert tracker.calibration_path == latest


def test_unreadable_selection_does_not_retain_previous_geometry(tmp_path: Path) -> None:
    source = build_loaded_tracker().calibration
    assert source is not None
    path = tmp_path / 'selected.toml'
    source.save_toml(path=path)
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
    frames = [{camera_id: Observation(frame_number=0, image_size=(720, 1280), stages={
        'body': StageObservation(name='body', keypoints=Keypoints(names=('left_wrist',),
            xyz=np.array([[10., 20., 0.]]), visibility=np.ones(1)))
    }) for camera_id in metadata}]
    with pytest.raises(ValueError, match='explicitly selected calibration'):
        run_posthoc_mocap_task(
            frame_observations=frames, recording_info=recording, video_metadata=metadata,
            task_config=PosthocMocapPipelineConfig(calibration_toml_path=None), selected_board=None,
        )
