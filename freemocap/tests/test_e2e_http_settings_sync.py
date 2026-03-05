"""
End-to-end HTTP integration tests.

Tests the full request path from frontend URL → FastAPI router (with real
prefixes) → SettingsManager → pipeline sync. Unlike the unit tests in
test_http_config_endpoints.py which test individual routers in isolation,
these tests mount routers at the same prefixes the real app uses
(/freemocap/calibration/..., /freemocap/mocap/...) and verify the full
flow through a single app instance.

What these catch that unit tests don't:
  - Route prefix mounting issues (e.g. double-prefix bugs)
  - Cross-router interactions through a shared SettingsManager
  - Settings version monotonicity across multiple endpoint calls
  - Full serialization round-trip with real Pydantic validation
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from freemocap.core.pipeline.pipeline_configs import MocapPipelineConfig
from freemocap.tests.conftest import MockFreemocapApp


# ---------------------------------------------------------------------------
# Calibration config update: full route path
# ---------------------------------------------------------------------------


class TestCalibrationConfigFullRoute:
    """Verify /freemocap/calibration/config/update/all works end-to-end."""

    def test_config_update_at_real_prefix(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        """The frontend hits /freemocap/calibration/config/update/all."""
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = e2e_client.post(
                "/freemocap/calibration/config/update/all",
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
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_config_update_propagates_to_settings_manager(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            e2e_client.post(
                "/freemocap/calibration/config/update/all",
                json={
                    "config": {
                        "charucoBoardXSquares": 11,
                        "charucoBoardYSquares": 9,
                        "charucoSquareLength": 30.0,
                        "solverMethod": "anipose",
                        "useGroundplane": False,
                    },
                },
            )
        cal = mock_app.settings_manager.settings.calibration.config
        assert cal.charuco_board_x_squares == 11
        assert cal.charuco_board_y_squares == 9
        assert cal.charuco_square_length == 30.0

    def test_config_update_syncs_to_pipeline(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            e2e_client.post(
                "/freemocap/calibration/config/update/all",
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
        pipeline = mock_app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 1
        synced = pipeline.update_config_calls[0]
        assert synced.calibration_config.charuco_board_x_squares == 7

    def test_invalid_config_returns_422(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = e2e_client.post(
                "/freemocap/calibration/config/update/all",
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


# ---------------------------------------------------------------------------
# Mocap config update: full route path
# ---------------------------------------------------------------------------


class TestMocapConfigFullRoute:
    """Verify /freemocap/mocap/config/update/all works end-to-end."""

    def test_config_update_at_real_prefix(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        config = MocapPipelineConfig.default_realtime().model_dump()
        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = e2e_client.post(
                "/freemocap/mocap/config/update/all",
                json={"config": config},
            )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_config_update_propagates_to_settings_manager(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        config = MocapPipelineConfig.default_realtime().model_dump()
        config["skeleton_filter"]["beta"] = 0.99
        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            e2e_client.post(
                "/freemocap/mocap/config/update/all",
                json={"config": config},
            )
        assert mock_app.settings_manager.settings.mocap.config.skeleton_filter.beta == 0.99


# ---------------------------------------------------------------------------
# Cross-router interactions through shared SettingsManager
# ---------------------------------------------------------------------------


class TestCrossRouterSettingsSync:
    """
    Verify that config updates through different routers go through the
    same SettingsManager and produce monotonically increasing versions.
    """

    def test_version_increases_across_calibration_and_mocap_updates(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        assert mock_app.settings_manager.version == 0

        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ), patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            # First: calibration update
            e2e_client.post(
                "/freemocap/calibration/config/update/all",
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
            version_after_cal = mock_app.settings_manager.version

            # Second: mocap update
            config = MocapPipelineConfig.default_realtime().model_dump()
            e2e_client.post(
                "/freemocap/mocap/config/update/all",
                json={"config": config},
            )
            version_after_mocap = mock_app.settings_manager.version

        assert version_after_cal >= 1
        assert version_after_mocap > version_after_cal

    def test_calibration_update_does_not_clobber_mocap(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        """Updating calibration config must not touch mocap config."""
        original_mocap = mock_app.settings_manager.settings.mocap.model_dump()

        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            e2e_client.post(
                "/freemocap/calibration/config/update/all",
                json={
                    "config": {
                        "charucoBoardXSquares": 11,
                        "charucoBoardYSquares": 9,
                        "charucoSquareLength": 50.0,
                        "solverMethod": "pyceres",
                        "useGroundplane": True,
                    },
                },
            )

        assert mock_app.settings_manager.settings.mocap.model_dump() == original_mocap

    def test_mocap_update_does_not_clobber_calibration(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        """Updating mocap config must not touch calibration config."""
        # First set calibration to non-default values
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            e2e_client.post(
                "/freemocap/calibration/config/update/all",
                json={
                    "config": {
                        "charucoBoardXSquares": 11,
                        "charucoBoardYSquares": 9,
                        "charucoSquareLength": 50.0,
                        "solverMethod": "pyceres",
                        "useGroundplane": True,
                    },
                },
            )

        cal_after_first = mock_app.settings_manager.settings.calibration.model_dump()

        # Now update mocap
        config = MocapPipelineConfig.default_realtime().model_dump()
        config["skeleton_filter"]["beta"] = 0.5
        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            e2e_client.post(
                "/freemocap/mocap/config/update/all",
                json={"config": config},
            )

        assert mock_app.settings_manager.settings.calibration.model_dump() == cal_after_first


# ---------------------------------------------------------------------------
# Frontend payload format: exact JSON shapes from thunks
# ---------------------------------------------------------------------------


class TestFrontendURLPaths:
    """
    Verify the exact URLs the frontend ServerUrls class constructs
    actually resolve to valid endpoints.
    """

    def test_calibration_start_recording_url_resolves(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        """
        Frontend uses: `${baseUrl}/freemocap/calibration/recording/start`
        Should not 404. May 500 (no cameras) but must not 404 or 422.
        """
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            mock_app.start_recording_all = lambda **kwargs: None
            response = e2e_client.post(
                "/freemocap/calibration/recording/start",
                json={
                    "calibrationRecordingDirectory": "/tmp/test_cal",
                    "calibrationTaskConfig": {
                        "charucoBoardXSquares": 5,
                        "charucoBoardYSquares": 3,
                        "charucoSquareLength": 1,
                        "solverMethod": "anipose",
                        "useGroundplane": False,
                    },
                },
            )
        assert response.status_code != 404
        assert response.status_code != 422

    def test_mocap_start_recording_url_resolves(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        """
        Frontend uses: `${baseUrl}/freemocap/mocap/recording/start`
        """
        config = MocapPipelineConfig.default_realtime().model_dump()
        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            mock_app.start_recording_all = lambda **kwargs: None
            response = e2e_client.post(
                "/freemocap/mocap/recording/start",
                json={
                    "mocapRecordingDirectory": "/tmp/test_mocap",
                    "mocapTaskConfig": config,
                },
            )
        assert response.status_code != 404
        assert response.status_code != 422

    def test_calibration_config_update_url_resolves(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        """
        Frontend uses: `${baseUrl}/freemocap/calibration/config/update/all`
        """
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = e2e_client.post(
                "/freemocap/calibration/config/update/all",
                json={
                    "config": {
                        "charucoBoardXSquares": 5,
                        "charucoBoardYSquares": 3,
                        "charucoSquareLength": 1,
                        "solverMethod": "anipose",
                        "useGroundplane": False,
                    },
                },
            )
        assert response.status_code == 200

    def test_mocap_config_update_url_resolves(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        """
        Frontend uses: `${baseUrl}/freemocap/mocap/config/update/all`
        """
        config = MocapPipelineConfig.default_realtime().model_dump()
        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = e2e_client.post(
                "/freemocap/mocap/config/update/all",
                json={"config": config},
            )
        assert response.status_code == 200
