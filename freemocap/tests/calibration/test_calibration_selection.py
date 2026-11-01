"""Null selects the latest calibration; explicit paths cannot silently fall back."""

from pathlib import Path
import os

import pytest

from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.core.tasks.calibration.shared import calibration_paths
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
