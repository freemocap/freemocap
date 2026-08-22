from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi.testclient import TestClient
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.api.http.calibration.calibration_router import calibration_router
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
)


@pytest.fixture
def mock_app():
    """Mock FreemocapApplication with a realtime pipeline that has pubsub."""
    app = MagicMock()
    app.start_recording_all = AsyncMock()
    app.stop_recording_all = AsyncMock(
        return_value=RecordingInfo(
            recording_directory="/tmp/test",
            recording_name="test_recording",
        )
    )
    app.create_posthoc_calibration_pipeline = AsyncMock(
        return_value=MagicMock(id="pipe_123")
    )

    # Mock realtime pipeline manager with one alive pipeline
    mock_pipeline = MagicMock()
    mock_pipeline.alive = True
    mock_pipeline.pubsub = MagicMock()
    mock_pipeline.pubsub.publish = MagicMock()

    app.realtime_pipeline_manager = MagicMock()
    app.realtime_pipeline_manager.pipelines = {"pipe_1": mock_pipeline}

    return app


@pytest.fixture
def client(mock_app):
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(calibration_router)

    with patch(
        "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
        return_value=mock_app,
    ):
        with patch(
            "freemocap.api.http.calibration.calibration_router._reject_if_recording_directory_not_empty",
            return_value=None,
        ):
            yield TestClient(test_app)


class TestCalibrationRecordingStatePublishing:
    def test_start_publishes_recording_state(self, client, mock_app):
        """POST /calibration/recording/start publishes is_active=True."""
        response = client.post(
            "/calibration/recording/start",
            json={
                "calibrationTaskConfig": {
                    "charucoBoard": {
                        "squares_x": 7,
                        "squares_y": 5,
                        "square_length_mm": 54,
                        "marker_length_ratio": 0.8,
                        "aruco_dictionary_enum": 10,  # cv2.aruco.DICT_4X4_250
                    }
                },
                "calibrationRecordingDirectory": "/tmp/test",
            },
        )
        assert response.status_code == 200

        # Verify publish was called on each alive pipeline
        for pipeline in mock_app.realtime_pipeline_manager.pipelines.values():
            pipeline.pubsub.publish.assert_called()
            call_args = pipeline.pubsub.publish.call_args
            # topic_type should be CalibrationRecordingStateTopic
            assert call_args[0][0] is CalibrationRecordingStateTopic
            # message should be CalibrationRecordingStateMessage(is_active=True)
            assert isinstance(call_args[0][1], CalibrationRecordingStateMessage)
            assert call_args[0][1].is_active is True


class TestCalibrationStatus:
    def test_missing_calibration_is_explicit(self, client, tmp_path):
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_last_successful_calibration_toml_path",
            return_value=tmp_path / "missing.toml",
        ):
            response = client.get("/calibration/status")
        assert response.status_code == 200
        assert response.json() == {
            "state": "missing",
            "path": None,
            "camera_ids": [],
            "reprojection_error_px": None,
            "accepted": False,
            "updated_at_ms": None,
            "error": None,
        }

    def test_reports_camera_set_and_quality_threshold(self, client, tmp_path):
        calibration_path = tmp_path / "calibration.toml"
        calibration_path.write_text("fixture")
        calibration = MagicMock(
            camera_ids=["cam-a", "cam-b"], reprojection_error_px=1.25
        )
        with (
            patch(
                "freemocap.api.http.calibration.calibration_router.get_last_successful_calibration_toml_path",
                return_value=calibration_path,
            ),
            patch(
                "freemocap.api.http.calibration.calibration_router.CalibrationResult.load_anipose_toml",
                return_value=calibration,
            ),
        ):
            response = client.get("/calibration/status")
        assert response.status_code == 200
        assert response.json()["state"] == "ready"
        assert response.json()["camera_ids"] == ["cam-a", "cam-b"]
        assert response.json()["reprojection_error_px"] == 1.25
        assert response.json()["accepted"] is True

    def test_stop_publishes_recording_state(self, client, mock_app):
        """POST /calibration/recording/stop publishes is_active=False."""
        response = client.post(
            "/calibration/recording/stop",
            json={
                "calibrationTaskConfig": {
                    "charucoBoard": {
                        "squares_x": 7,
                        "squares_y": 5,
                        "square_length_mm": 54,
                        "marker_length_ratio": 0.8,
                        "aruco_dictionary_enum": 10,  # cv2.aruco.DICT_4X4_250
                    }
                },
            },
        )
        assert response.status_code == 200

        # Verify publish was called on each alive pipeline
        for pipeline in mock_app.realtime_pipeline_manager.pipelines.values():
            pipeline.pubsub.publish.assert_called()
            call_args = pipeline.pubsub.publish.call_args
            assert call_args[0][0] is CalibrationRecordingStateTopic
            assert isinstance(call_args[0][1], CalibrationRecordingStateMessage)
            assert call_args[0][1].is_active is False
