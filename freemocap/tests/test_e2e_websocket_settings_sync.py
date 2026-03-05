"""
End-to-end WebSocket integration tests.

Tests the full round-trip: client connects via WebSocket → receives initial
settings/state → sends settings/patch → receives updated settings/state with
bumped version. Also tests settings/request and malformed message handling.

What these catch that unit tests don't:
  - WebSocket JSON serialization/deserialization through real Starlette transport
  - Settings relay actually waking up and pushing after a patch
  - Version monotonicity across multiple patches in a single connection
  - The full message_type routing in the WebSocket handler
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from freemocap.tests.conftest import MockFreemocapApp


# ---------------------------------------------------------------------------
# WebSocket connection + initial state
# ---------------------------------------------------------------------------


class TestWebSocketInitialState:
    """Verify the WebSocket pushes initial settings/state on connect."""

    def test_receives_initial_settings_state_on_connect(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            msg = ws.receive_json()
            assert msg["message_type"] == "settings/state"
            assert isinstance(msg["settings"], dict)
            assert isinstance(msg["version"], int)

    def test_initial_state_has_all_top_level_keys(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            msg = ws.receive_json()
            settings = msg["settings"]
            assert "cameras" in settings
            assert "pipeline" in settings
            assert "calibration" in settings
            assert "mocap" in settings
            assert "vmc" in settings

    def test_initial_version_is_zero(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            msg = ws.receive_json()
            assert msg["version"] == 0


# ---------------------------------------------------------------------------
# WebSocket settings/patch → settings/state round-trip
# ---------------------------------------------------------------------------


class TestWebSocketPatchRoundTrip:
    """Send settings/patch via WebSocket, verify settings/state comes back."""

    def test_patch_calibration_is_recording(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            initial = ws.receive_json()
            assert initial["settings"]["calibration"]["is_recording"] is False

            ws.send_json({
                "message_type": "settings/patch",
                "patch": {"calibration": {"is_recording": True}},
            })

            updated = ws.receive_json()
            assert updated["message_type"] == "settings/state"
            assert updated["version"] > initial["version"]
            assert updated["settings"]["calibration"]["is_recording"] is True

    def test_patch_calibration_config(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            initial = ws.receive_json()

            ws.send_json({
                "message_type": "settings/patch",
                "patch": {
                    "calibration": {
                        "config": {"charuco_board_x_squares": 11},
                    },
                },
            })

            updated = ws.receive_json()
            cal_config = updated["settings"]["calibration"]["config"]
            assert cal_config["charuco_board_x_squares"] == 11
            # Sibling fields preserved
            assert cal_config["charuco_board_y_squares"] == 3

    def test_patch_mocap_filter_beta(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            ws.receive_json()  # initial

            ws.send_json({
                "message_type": "settings/patch",
                "patch": {
                    "mocap": {
                        "config": {
                            "skeleton_filter": {"beta": 0.99},
                        },
                    },
                },
            })

            updated = ws.receive_json()
            skeleton_filter = updated["settings"]["mocap"]["config"]["skeleton_filter"]
            assert skeleton_filter["beta"] == 0.99
            # Sibling fields preserved
            assert skeleton_filter["min_cutoff"] == 0.005

    def test_patch_preserves_unrelated_sections(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        """Patching calibration must not affect mocap."""
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            initial = ws.receive_json()
            original_mocap = initial["settings"]["mocap"]

            ws.send_json({
                "message_type": "settings/patch",
                "patch": {"calibration": {"is_recording": True}},
            })

            updated = ws.receive_json()
            assert updated["settings"]["mocap"] == original_mocap


# ---------------------------------------------------------------------------
# WebSocket settings/patch syncs to pipelines
# ---------------------------------------------------------------------------


class TestWebSocketPatchPipelineSync:
    """Verify that config patches via WebSocket sync to running pipelines."""

    def test_calibration_config_patch_syncs_to_pipeline(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            ws.receive_json()  # initial

            ws.send_json({
                "message_type": "settings/patch",
                "patch": {
                    "calibration": {
                        "config": {"charuco_board_x_squares": 13},
                    },
                },
            })

            ws.receive_json()  # updated state

        pipeline = mock_app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 1

    def test_mocap_config_patch_syncs_to_pipeline(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            ws.receive_json()  # initial

            ws.send_json({
                "message_type": "settings/patch",
                "patch": {
                    "mocap": {
                        "config": {
                            "skeleton_filter": {"beta": 0.1},
                        },
                    },
                },
            })

            ws.receive_json()  # updated state

        pipeline = mock_app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 1

    def test_status_only_patch_does_not_sync_pipeline(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        """Patching only is_recording should NOT touch pipelines."""
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            ws.receive_json()

            ws.send_json({
                "message_type": "settings/patch",
                "patch": {"calibration": {"is_recording": True}},
            })

            ws.receive_json()

        pipeline = mock_app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 0


# ---------------------------------------------------------------------------
# Version monotonicity across multiple patches
# ---------------------------------------------------------------------------


class TestWebSocketVersionMonotonicity:
    """Verify versions always increase across multiple patches."""

    def test_multiple_patches_produce_increasing_versions(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            initial = ws.receive_json()
            versions = [initial["version"]]

            for i in range(5):
                ws.send_json({
                    "message_type": "settings/patch",
                    "patch": {
                        "calibration": {"recording_progress": float(i * 10)},
                    },
                })
                msg = ws.receive_json()
                versions.append(msg["version"])

        for i in range(1, len(versions)):
            assert versions[i] > versions[i - 1], (
                f"Version did not increase: {versions}"
            )


# ---------------------------------------------------------------------------
# WebSocket settings/request
# ---------------------------------------------------------------------------


class TestWebSocketSettingsRequest:
    """Verify settings/request triggers a full state push."""

    def test_request_triggers_state_push(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with e2e_client.websocket_connect("/websocket/connect") as ws:
            initial = ws.receive_json()

            ws.send_json({"message_type": "settings/request"})

            response = ws.receive_json()
            assert response["message_type"] == "settings/state"
            # Version should have bumped (request triggers notify_changed)
            assert response["version"] > initial["version"]


# ---------------------------------------------------------------------------
# HTTP config update triggers WebSocket state push
# ---------------------------------------------------------------------------


class TestHTTPToWebSocketRoundTrip:
    """
    The highest-value E2E test: an HTTP POST to a config endpoint triggers
    a settings/state push on the WebSocket with the correct updated values.

    This is exactly what happens in the real app: the frontend sends an HTTP
    POST via a thunk, and the SettingsManager.apply_patch() call inside the
    router notifies the WebSocket relay, which pushes the updated state back.
    """

    def test_http_calibration_update_pushes_websocket_state(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        with patch(
            "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
            return_value=mock_app,
        ):
            with e2e_client.websocket_connect("/websocket/connect") as ws:
                initial = ws.receive_json()
                assert initial["version"] == 0

                # HTTP POST from frontend thunk
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

                # WebSocket should receive updated state
                updated = ws.receive_json()
                assert updated["message_type"] == "settings/state"
                assert updated["version"] > 0

                cal = updated["settings"]["calibration"]["config"]
                assert cal["charuco_board_x_squares"] == 9
                assert cal["charuco_board_y_squares"] == 7
                assert cal["charuco_square_length"] == 25.0
                assert cal["solver_method"] == "pyceres"
                assert cal["use_groundplane"] is True

    def test_http_mocap_update_pushes_websocket_state(
        self,
        e2e_client: TestClient,
        mock_app: MockFreemocapApp,
    ) -> None:
        from freemocap.core.pipeline.pipeline_configs import MocapPipelineConfig

        config = MocapPipelineConfig.default_realtime().model_dump()
        config["skeleton_filter"]["beta"] = 0.42

        with patch(
            "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
            return_value=mock_app,
        ):
            with e2e_client.websocket_connect("/websocket/connect") as ws:
                ws.receive_json()  # initial

                response = e2e_client.post(
                    "/freemocap/mocap/config/update/all",
                    json={"config": config},
                )
                assert response.status_code == 200

                updated = ws.receive_json()
                skeleton_filter = updated["settings"]["mocap"]["config"]["skeleton_filter"]
                assert skeleton_filter["beta"] == 0.42
