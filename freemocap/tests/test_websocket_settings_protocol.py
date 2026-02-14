"""
WebSocket settings protocol tests: verify handle_settings_message routing,
patch application, pipeline sync, and the settings_state_relay push loop.
"""
import asyncio
import json
import threading
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from freemocap.app.settings import SettingsManager
from freemocap.app.settings_protocol import (
    _sync_patch_to_app,
    handle_settings_message,
    settings_state_relay,
)
from freemocap.core.pipeline.pipeline_configs import (
    CalibrationPipelineConfig,
    MocapPipelineConfig,
)


from starlette.websockets import WebSocketState


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockPipeline:
    def __init__(self) -> None:
        self.config = MagicMock()
        self.config.calibration_config = CalibrationPipelineConfig()
        self.config.mocap_config = MocapPipelineConfig.default_realtime()
        self.update_config_calls: list[Any] = []

    def update_config(self, new_config: Any) -> None:
        self.update_config_calls.append(deepcopy(new_config))


class MockPipelineManager:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.pipeline = MockPipeline()
        self.pipelines: dict[str, MockPipeline] = {"test": self.pipeline}


class MockApp:
    def __init__(self) -> None:
        self.settings_manager = SettingsManager()
        self.realtime_pipeline_manager = MockPipelineManager()


class FakeWebSocket:
    """Minimal WebSocket mock that records sent messages.
    Uses the real WebSocketState enum so comparisons in the relay work."""

    def __init__(self) -> None:
        self.client_state = WebSocketState.CONNECTED
        self.sent_json: list[dict[str, Any]] = []

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent_json.append(data)


# ---------------------------------------------------------------------------
# handle_settings_message
# ---------------------------------------------------------------------------


class TestHandleSettingsMessage:

    def test_patch_applies_to_settings_manager(self) -> None:
        app = MockApp()
        manager = app.settings_manager
        handle_settings_message(
            data={
                "message_type": "settings/patch",
                "patch": {"calibration": {"is_recording": True}},
            },
            settings_manager=manager,
            app=app,
        )
        assert manager.settings.calibration.is_recording is True

    def test_patch_bumps_version(self) -> None:
        app = MockApp()
        manager = app.settings_manager
        assert manager.version == 0
        handle_settings_message(
            data={
                "message_type": "settings/patch",
                "patch": {"calibration": {"is_recording": True}},
            },
            settings_manager=manager,
            app=app,
        )
        assert manager.version >= 1

    def test_patch_with_calibration_config_syncs_to_pipelines(self) -> None:
        app = MockApp()
        handle_settings_message(
            data={
                "message_type": "settings/patch",
                "patch": {
                    "calibration": {
                        "config": {"charuco_board_x_squares": 9},
                    },
                },
            },
            settings_manager=app.settings_manager,
            app=app,
        )
        pipeline = app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 1

    def test_patch_with_mocap_config_syncs_to_pipelines(self) -> None:
        app = MockApp()
        handle_settings_message(
            data={
                "message_type": "settings/patch",
                "patch": {
                    "mocap": {
                        "config": {
                            "skeleton_filter": {"beta": 0.99},
                        },
                    },
                },
            },
            settings_manager=app.settings_manager,
            app=app,
        )
        pipeline = app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 1

    def test_patch_without_config_does_not_sync_pipelines(self) -> None:
        """Patching only status fields should not trigger pipeline sync."""
        app = MockApp()
        handle_settings_message(
            data={
                "message_type": "settings/patch",
                "patch": {"calibration": {"is_recording": True}},
            },
            settings_manager=app.settings_manager,
            app=app,
        )
        pipeline = app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 0

    def test_request_triggers_notify(self) -> None:
        app = MockApp()
        manager = app.settings_manager
        initial_version = manager.version
        handle_settings_message(
            data={"message_type": "settings/request"},
            settings_manager=manager,
            app=app,
        )
        assert manager.version == initial_version + 1

    def test_unknown_type_raises(self) -> None:
        app = MockApp()
        with pytest.raises(ValueError, match="Unknown settings message_type"):
            handle_settings_message(
                data={"message_type": "settings/bogus"},
                settings_manager=app.settings_manager,
                app=app,
            )

    def test_patch_missing_patch_field_raises(self) -> None:
        app = MockApp()
        with pytest.raises(ValueError, match="no 'patch' field"):
            handle_settings_message(
                data={"message_type": "settings/patch"},
                settings_manager=app.settings_manager,
                app=app,
            )


# ---------------------------------------------------------------------------
# _sync_patch_to_app
# ---------------------------------------------------------------------------


class TestSyncPatchToApp:

    def test_calibration_config_patch_syncs(self) -> None:
        app = MockApp()
        # First apply the patch to the settings manager so it has the new config
        app.settings_manager.apply_patch({
            "calibration": {"config": {"charuco_board_x_squares": 11}},
        })
        _sync_patch_to_app(
            patch={"calibration": {"config": {"charuco_board_x_squares": 11}}},
            settings_manager=app.settings_manager,
            app=app,
        )
        pipeline = app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 1

    def test_mocap_config_patch_syncs(self) -> None:
        app = MockApp()
        app.settings_manager.apply_patch({
            "mocap": {"config": {"skeleton_filter": {"beta": 0.1}}},
        })
        _sync_patch_to_app(
            patch={"mocap": {"config": {"skeleton_filter": {"beta": 0.1}}}},
            settings_manager=app.settings_manager,
            app=app,
        )
        pipeline = app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 1

    def test_non_config_patch_does_not_sync(self) -> None:
        app = MockApp()
        _sync_patch_to_app(
            patch={"calibration": {"is_recording": True}},
            settings_manager=app.settings_manager,
            app=app,
        )
        pipeline = app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 0

    def test_unrelated_patch_does_not_sync(self) -> None:
        app = MockApp()
        _sync_patch_to_app(
            patch={"cameras": {}},
            settings_manager=app.settings_manager,
            app=app,
        )
        pipeline = app.realtime_pipeline_manager.pipeline
        assert len(pipeline.update_config_calls) == 0


# ---------------------------------------------------------------------------
# settings_state_relay
# ---------------------------------------------------------------------------


class TestSettingsStateRelay:

    @pytest.mark.asyncio
    async def test_sends_initial_state_on_startup(self) -> None:
        manager = SettingsManager()
        ws = FakeWebSocket()
        stop = False

        async def run_relay() -> None:
            await settings_state_relay(
                websocket=ws,
                settings_manager=manager,
                should_continue=lambda: not stop,
            )

        task = asyncio.create_task(run_relay())
        await asyncio.sleep(0.05)
        stop = True
        manager.notify_changed()  # Wake the relay so it exits
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(ws.sent_json) >= 1
        first_msg = ws.sent_json[0]
        assert first_msg["message_type"] == "settings/state"
        assert "settings" in first_msg
        assert "version" in first_msg

    @pytest.mark.asyncio
    async def test_sends_update_on_change(self) -> None:
        manager = SettingsManager()
        ws = FakeWebSocket()
        stop = False

        async def run_relay() -> None:
            await settings_state_relay(
                websocket=ws,
                settings_manager=manager,
                should_continue=lambda: not stop,
            )

        task = asyncio.create_task(run_relay())
        await asyncio.sleep(0.05)

        # Trigger a change
        manager.apply_patch({"calibration": {"is_recording": True}})
        await asyncio.sleep(0.05)

        stop = True
        manager.notify_changed()  # Wake relay to exit
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have at least 2 messages: initial + one change
        assert len(ws.sent_json) >= 2
        last_msg = ws.sent_json[-1]
        assert last_msg["message_type"] == "settings/state"
        assert last_msg["version"] >= 1

    @pytest.mark.asyncio
    async def test_version_increases_monotonically(self) -> None:
        manager = SettingsManager()
        ws = FakeWebSocket()
        stop = False

        async def run_relay() -> None:
            await settings_state_relay(
                websocket=ws,
                settings_manager=manager,
                should_continue=lambda: not stop,
            )

        task = asyncio.create_task(run_relay())
        await asyncio.sleep(0.05)

        for i in range(3):
            manager.apply_patch({"calibration": {"recording_progress": float(i * 10)}})
            await asyncio.sleep(0.05)

        stop = True
        manager.notify_changed()
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        versions = [msg["version"] for msg in ws.sent_json]
        for i in range(1, len(versions)):
            assert versions[i] >= versions[i - 1], (
                f"Version went backwards: {versions}"
            )
