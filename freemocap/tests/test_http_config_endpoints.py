"""
HTTP endpoint integration tests: verify that the calibration, mocap, and
pipeline routers accept the payloads the frontend sends and correctly
update the SettingsManager.

Uses FastAPI TestClient with a mocked FreemocapApplication.
"""
import threading
from copy import deepcopy
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from freemocap.core.pipeline.pipeline_configs import (
    CalibrationPipelineConfig,
    MocapPipelineConfig,
)

from freemocap.api.http.calibration.calibration_router import calibration_router
from freemocap.api.http.mocap.mocap_router import mocap_router
from freemocap.app.settings import SettingsManager


# ---------------------------------------------------------------------------
# Mock pipeline for testing config sync
# ---------------------------------------------------------------------------


class MockPipeline:
    """Minimal mock of a RealtimePipeline that records update_config calls."""

    def __init__(self) -> None:
        self.config = MagicMock()
        self.config.calibration_config = CalibrationPipelineConfig()
        self.config.mocap_config = MocapPipelineConfig.default_realtime()
        self.update_config_calls: list[Any] = []

    def update_config(self, new_config: Any) -> None:
        self.update_config_calls.append(deepcopy(new_config))


class MockPipelineManager:
    """Minimal mock of RealtimePipelineManager."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.pipeline = MockPipeline()
        self.pipelines: dict[str, MockPipeline] = {"test-pipeline": self.pipeline}


class MockApp:
    """Minimal mock of FreemocapApplication with a real SettingsManager."""

    def __init__(self) -> None:
        self.settings_manager = SettingsManager()
        self.realtime_pipeline_manager = MockPipelineManager()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_app() -> MockApp:
    return MockApp()


@pytest.fixture
def test_client(mock_app: MockApp) -> TestClient:
    """Create a FastAPI TestClient with calibration and mocap routers,
    using a mocked FreemocapApplication."""
    app = FastAPI()
    app.include_router(calibration_router)
    app.include_router(mocap_router)

    with patch(
        "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
        return_value=mock_app,
    ), patch(
        "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
        return_value=mock_app,
    ):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# Calibration config update
# ---------------------------------------------------------------------------


class TestCalibrationConfigUpdateEndpoint:

    def test_returns_success(self, test_client: TestClient, mock_app: MockApp) -> None:
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post(
                "/calibration/config/update/all",
                json={
                    "config": {
                        "charucoBoardXSquares": 7,
                        "charucoBoardYSquares": 5,
                        "charucoSquareLength": 39.0,
                        "solverMethod": "anipose",
                        "useGroundplane": False,
                    },
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_patches_settings_manager(self, test_client: TestClient, mock_app: MockApp) -> None:
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            test_client.post(
                "/calibration/config/update/all",
                json={
                    "config": {
                        "charucoBoardXSquares": 7,
                        "charucoBoardYSquares": 5,
                        "charucoSquareLength": 39.0,
                        "solverMethod": "anipose",
                        "useGroundplane": False,
                    },
                },
            )
        settings = mock_app.settings_manager.settings
        assert settings.calibration.config.charuco_board_x_squares == 7
        assert settings.calibration.config.charuco_board_y_squares == 5
        assert settings.calibration.config.charuco_square_length == 39.0

    def test_syncs_to_pipelines(self, test_client: TestClient, mock_app: MockApp) -> None:
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            test_client.post(
                "/calibration/config/update/all",
                json={
                    "config": {
                        "charucoBoardXSquares": 9,
                        "charucoBoardYSquares": 7,
                        "charucoSquareLength": 25.0,
                        "solverMethod": "pyceres",
                        "useGroundplane": True,
                    },
                },
            )
        pipeline = mock_app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 1
        synced_config = pipeline.update_config_calls[0]
        assert synced_config.calibration_config.charuco_board_x_squares == 9
        assert synced_config.calibration_config.use_groundplane is True

    def test_bumps_settings_version(self, test_client: TestClient, mock_app: MockApp) -> None:
        assert mock_app.settings_manager.version == 0
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            test_client.post(
                "/calibration/config/update/all",
                json={
                    "config": {
                        "charucoBoardXSquares": 7,
                        "charucoBoardYSquares": 5,
                        "charucoSquareLength": 39.0,
                        "solverMethod": "anipose",
                        "useGroundplane": False,
                    },
                },
            )
        assert mock_app.settings_manager.version >= 1

    def test_rejects_invalid_config(self, test_client: TestClient, mock_app: MockApp) -> None:
        """charuco_board_x_squares must be > 0."""
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post(
                "/calibration/config/update/all",
                json={
                    "config": {
                        "charucoBoardXSquares": -1,
                        "charucoBoardYSquares": 5,
                        "charucoSquareLength": 39.0,
                        "solverMethod": "anipose",
                        "useGroundplane": False,
                    },
                },
            )
        assert response.status_code == 422

    def test_rejects_missing_config(self, test_client: TestClient, mock_app: MockApp) -> None:
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post(
                "/calibration/config/update/all",
                json={},
            )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Mocap config update
# ---------------------------------------------------------------------------


class TestMocapConfigUpdateEndpoint:

    @pytest.fixture
    def default_mocap_config_payload(self) -> dict[str, Any]:
        return {
            "config": MocapPipelineConfig.default_realtime().model_dump(),
        }

    def test_returns_success(
        self,
        test_client: TestClient,
        mock_app: MockApp,
        default_mocap_config_payload: dict[str, Any],
    ) -> None:
        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post(
                "/mocap/config/update/all",
                json=default_mocap_config_payload,
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_patches_settings_manager(
        self,
        test_client: TestClient,
        mock_app: MockApp,
    ) -> None:
        config = MocapPipelineConfig.default_realtime()
        payload = config.model_dump()
        # Modify a value to verify it propagates
        payload["skeleton_filter"]["beta"] = 0.99

        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            test_client.post("/mocap/config/update/all", json={"config": payload})

        settings = mock_app.settings_manager.settings
        assert settings.mocap.config.realtime_filter_config.beta == 0.99

    def test_syncs_to_pipelines(
        self,
        test_client: TestClient,
        mock_app: MockApp,
    ) -> None:
        config = MocapPipelineConfig.default_realtime()
        payload = config.model_dump()
        payload["skeleton_filter"]["max_rejected_streak"] = 10

        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            test_client.post("/mocap/config/update/all", json={"config": payload})

        pipeline = mock_app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 1

    def test_bumps_settings_version(
        self,
        test_client: TestClient,
        mock_app: MockApp,
        default_mocap_config_payload: dict[str, Any],
    ) -> None:
        assert mock_app.settings_manager.version == 0
        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            test_client.post("/mocap/config/update/all", json=default_mocap_config_payload)
        assert mock_app.settings_manager.version >= 1


# ---------------------------------------------------------------------------
# Frontend payload format compatibility
# ---------------------------------------------------------------------------


class TestFrontendPayloadFormat:
    """Verify that the exact JSON shapes the frontend thunks send
    are accepted by the backend endpoints."""

    def test_calibration_thunk_payload_accepted(
        self,
        test_client: TestClient,
        mock_app: MockApp,
    ) -> None:
        """Simulate the exact payload from updateCalibrationConfigOnServer thunk.
        The frontend sends { config: { ...camelCaseFields } }."""
        payload = {
            "config": {
                "charucoBoardXSquares": 5,
                "charucoBoardYSquares": 3,
                "charucoSquareLength": 1,
                "solverMethod": "anipose",
                "useGroundplane": False,
            },
        }
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post("/calibration/config/update/all", json=payload)
        assert response.status_code == 200

    def test_start_calibration_recording_payload_accepted(
        self,
        test_client: TestClient,
        mock_app: MockApp,
    ) -> None:
        """Simulate the payload from startCalibrationRecording thunk.
        Uses camelCase field aliases."""
        mock_app.start_recording_all = MagicMock()
        payload = {
            "calibrationRecordingDirectory": "/tmp/test_cal_recording",
            "calibrationTaskConfig": {
                "charucoBoardXSquares": 5,
                "charucoBoardYSquares": 3,
                "charucoSquareLength": 1,
                "solverMethod": "anipose",
                "useGroundplane": False,
            },
        }
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post("/calibration/recording/start", json=payload)
        # May fail at the actual start_recording (no real cameras), but should not be 422
        assert response.status_code != 422, (
            f"Got 422 validation error for frontend payload: {response.json()}"
        )

    def test_stop_calibration_recording_payload_accepted(
        self,
        test_client: TestClient,
        mock_app: MockApp,
    ) -> None:
        """Simulate the payload from stopCalibrationRecording thunk."""
        payload = {
            "calibrationTaskConfig": {
                "charucoBoardXSquares": 5,
                "charucoBoardYSquares": 3,
                "charucoSquareLength": 1,
                "solverMethod": "anipose",
                "useGroundplane": False,
            },
        }
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post("/calibration/recording/stop", json=payload)
        # May fail at actual stop (no recording), but should not be 422
        assert response.status_code != 422, (
            f"Got 422 validation error for frontend payload: {response.json()}"
        )

    def test_calibrate_recording_payload_accepted(
        self,
        test_client: TestClient,
        mock_app: MockApp,
    ) -> None:
        """Simulate the payload from calibrateRecording thunk."""
        payload = {
            "calibrationRecordingDirectory": "/tmp/test_cal_recording",
            "calibrationTaskConfig": {
                "charucoBoardXSquares": 5,
                "charucoBoardYSquares": 3,
                "charucoSquareLength": 1,
                "solverMethod": "anipose",
                "useGroundplane": False,
            },
        }
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post("/calibration/recording/calibrate", json=payload)
        assert response.status_code != 422, (
            f"Got 422 validation error for frontend payload: {response.json()}"
        )

    def test_mocap_start_recording_payload_accepted(
        self,
        test_client: TestClient,
        mock_app: MockApp,
    ) -> None:
        """Simulate the payload from startMocapRecording thunk."""
        config = MocapPipelineConfig.default_realtime().model_dump()
        payload = {
            "mocapRecordingDirectory": "/tmp/test_mocap_recording",
            "mocapTaskConfig": config,
        }
        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post("/mocap/recording/start", json=payload)
        assert response.status_code != 422, (
            f"Got 422 validation error for frontend payload: {response.json()}"
        )

    def test_mocap_stop_recording_payload_accepted(
        self,
        test_client: TestClient,
        mock_app: MockApp,
    ) -> None:
        """Simulate the payload from stopMocapRecording thunk."""
        config = MocapPipelineConfig.default_realtime().model_dump()
        payload = {
            "mocapTaskConfig": config,
        }
        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post("/mocap/recording/stop", json=payload)
        assert response.status_code != 422, (
            f"Got 422 validation error for frontend payload: {response.json()}"
        )
