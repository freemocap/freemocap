"""
Shared fixtures for end-to-end integration tests.

Builds a FastAPI app with the real routers mounted at the correct prefixes,
backed by a mock FreemocapApplication that has a real SettingsManager and
mock pipeline/camera managers. This lets us test the full HTTP→SettingsManager
→WebSocket round-trip without requiring camera hardware.
"""
import asyncio
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest
from fastapi import APIRouter, FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketState

from freemocap.api.http.calibration.calibration_router import calibration_router
from freemocap.api.http.mocap.mocap_router import mocap_router
from freemocap.app.settings import SettingsManager
from freemocap.app.settings_protocol import (
    handle_settings_message,
    settings_state_relay,
)
from freemocap.core.pipeline.pipeline_configs import (
    CalibrationPipelineConfig,
    MocapPipelineConfig,
)


# ---------------------------------------------------------------------------
# Mock application components
# ---------------------------------------------------------------------------


class MockPipeline:
    """Records update_config calls without touching real hardware."""

    def __init__(self) -> None:
        self.config = MagicMock()
        self.config.calibration_config = CalibrationPipelineConfig()
        self.config.mocap_config = MocapPipelineConfig.default_realtime()
        self.update_config_calls: list[object] = []

    def update_config(self, new_config: object) -> None:
        self.update_config_calls.append(deepcopy(new_config))


class MockPipelineManager:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.pipeline = MockPipeline()
        self.pipelines: dict[str, MockPipeline] = {"test-pipeline": self.pipeline}


@dataclass
class MockFreemocapApp:
    """Minimal mock that provides a real SettingsManager with mock hardware."""

    settings_manager: SettingsManager = field(default_factory=SettingsManager)
    realtime_pipeline_manager: MockPipelineManager = field(default_factory=MockPipelineManager)


# ---------------------------------------------------------------------------
# Simplified WebSocket endpoint for testing settings relay
# ---------------------------------------------------------------------------


def _create_settings_ws_router(mock_app: MockFreemocapApp) -> APIRouter:
    """
    Create a WebSocket router that runs only the settings relay and
    message handler — no image relay, no log relay, no camera hardware.
    """
    router = APIRouter()

    @router.websocket("/websocket/connect")
    async def settings_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        stop = False

        async def relay() -> None:
            await settings_state_relay(
                websocket=websocket,
                settings_manager=mock_app.settings_manager,
                should_continue=lambda: not stop,
            )

        relay_task = asyncio.create_task(relay())

        try:
            while not stop:
                message = await websocket.receive()
                msg_type = message.get("type", "")

                if msg_type == "websocket.disconnect":
                    stop = True
                    break

                if "text" in message:
                    import json

                    data = json.loads(message["text"])
                    data_message_type = data.get("message_type", "")
                    if data_message_type.startswith("settings/"):
                        handle_settings_message(
                            data=data,
                            settings_manager=mock_app.settings_manager,
                            app=mock_app,
                        )
        except Exception:
            stop = True
        finally:
            stop = True
            mock_app.settings_manager.notify_changed()
            relay_task.cancel()
            try:
                await relay_task
            except asyncio.CancelledError:
                pass

    return router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_app() -> MockFreemocapApp:
    return MockFreemocapApp()


@pytest.fixture
def e2e_app(mock_app: MockFreemocapApp) -> FastAPI:
    """
    Build a FastAPI app matching the real route structure:
      - /freemocap/calibration/...
      - /freemocap/mocap/...
      - /websocket/connect (settings-only, no hardware)
    """
    app = FastAPI()
    app.include_router(calibration_router, prefix="/freemocap")
    app.include_router(mocap_router, prefix="/freemocap")
    app.include_router(_create_settings_ws_router(mock_app))
    return app


@pytest.fixture
def e2e_client(e2e_app: FastAPI, mock_app: MockFreemocapApp) -> TestClient:
    """TestClient wired to the full E2E app with mocked get_freemocap_app."""
    with patch(
        "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
        return_value=mock_app,
    ), patch(
        "freemocap.api.http.mocap.mocap_router.get_freemocap_app",
        return_value=mock_app,
    ):
        yield TestClient(e2e_app)
