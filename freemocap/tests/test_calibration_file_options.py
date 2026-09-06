"""Recording-local calibration discovery is deterministic and independent of solving."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.calibration.calibration_router import calibration_router
from freemocap.core.tasks.calibration.shared.calibration_paths import find_recording_calibration


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
    assert response.json()["recording_path"] is None
