"""Recording-local calibration discovery is deterministic and independent of solving."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.calibration.calibration_router import calibration_router
from freemocap.core.tasks.calibration.shared.calibration_paths import find_recording_calibration
from freemocap.core.tasks.calibration.shared.calibration_save import save_calibration_copies


def test_local_calibration_precedence_and_ambiguity(tmp_path: Path) -> None:
    assert find_recording_calibration(recording_folder=tmp_path) is None
    first = tmp_path / "a_camera_calibration.toml"
    first.write_text("", encoding="utf-8")
    assert find_recording_calibration(recording_folder=tmp_path) == first
    (tmp_path / "b_camera_calibration.toml").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Multiple calibration"):
        find_recording_calibration(recording_folder=tmp_path)
    named = tmp_path / f"{tmp_path.name}_camera_calibration.toml"
    named.write_text("", encoding="utf-8")
    assert find_recording_calibration(recording_folder=tmp_path) == named


def test_calibration_options_allow_missing_calibration(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(calibration_router)
    with TestClient(app) as client:
        response = client.get("/calibration/files", params={"recording_directory": str(tmp_path)})
    assert response.status_code == 200
    assert response.json() == {"recording_path": None}


def test_most_recent_calibration_without_recording_selection(tmp_path: Path) -> None:
    path = tmp_path / 'latest.toml'
    app = FastAPI()
    app.include_router(calibration_router)
    with patch('freemocap.api.http.calibration.calibration_router.get_last_successful_calibration_toml_path', return_value=path):
        with TestClient(app) as client:
            missing = client.get('/calibration/most-recent')
            assert missing.status_code == 200
            assert missing.json() is None
            path.write_text('calibration', encoding='utf-8')
            selected = client.get('/calibration/most-recent')
            assert selected.status_code == 200
            assert selected.json() == str(path)


def test_save_and_discovery_share_configured_base_folder(tmp_path: Path) -> None:
    base = tmp_path / 'custom_data'
    (base / 'calibrations').mkdir(parents=True)
    recording = tmp_path / 'recording'
    recording.mkdir()
    app = FastAPI()
    app.include_router(calibration_router)

    def save_calibration(path: Path) -> None:
        path.write_text('successful calibration', encoding='utf-8')

    with patch('freemocap.core.tasks.calibration.shared.calibration_paths.get_default_freemocap_base_folder_path', return_value=str(base)):
        saved = save_calibration_copies(save_fn=save_calibration, recording_name='recording', recording_folder_path=recording)
        with TestClient(app) as client:
            response = client.get('/calibration/most-recent')
            assert response.status_code == 200
            latest = Path(response.json())
            assert latest.parent == base / 'calibrations'
            assert latest.read_text(encoding='utf-8') == saved.read_text(encoding='utf-8')
            local = client.get('/calibration/files', params={'recording_directory': str(recording)})
            assert local.json() == {'recording_path': str(saved)}
