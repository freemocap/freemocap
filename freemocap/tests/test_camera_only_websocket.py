"""Camera-only frame polling uses SkellyCam's group-local cursor contract."""

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
import pytest
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from starlette.websockets import WebSocket

from freemocap.api.websocket import websocket_server
from freemocap.api.websocket.websocket_server import WebsocketServer
from freemocap.app.freemocap_application import FreemocapApplication
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.producers.producer_contexts import StreamContext


@dataclass
class CameraPayload:
    id: str
    frame_number: int

    def get_latest_frontend_payload(
        self,
        *,
        if_newer_than: int,
        display_image_sizes: dict[str, dict[str, float]] | None,
    ) -> tuple[int, float, memoryview] | None:
        if self.frame_number <= if_newer_than:
            return None
        return self.frame_number, float(self.frame_number), memoryview(b"image")


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> WebsocketServer:
    manager = CameraGroupManager.__new__(CameraGroupManager)
    manager.closing = False
    manager.camera_groups = {}
    app = FreemocapApplication.__new__(FreemocapApplication)
    app.camera_group_manager = manager
    monkeypatch.setattr(websocket_server, "get_freemocap_app", lambda: app)
    monkeypatch.setattr(
        WebsocketServer,
        "_compose_current",
        lambda self: compose_messages(StreamContext(skeletons=())),
    )
    fastapi = FastAPI()
    fastapi.state.global_kill_flag = SimpleNamespace(value=False)
    result = WebsocketServer(
        fastapi_app=fastapi,
        websocket=WebSocket(
            scope={"type": "websocket"}, receive=AsyncMock(), send=AsyncMock()
        ),
    )
    monkeypatch.setattr(result, "_ensure_composition", AsyncMock())
    monkeypatch.setattr(result, "_record_framerate", Mock())
    monkeypatch.setattr(result, "_send_framerate_updates", AsyncMock())
    return result


async def test_empty_manager_accepts_initial_cursor(server: WebsocketServer) -> None:
    assert await server._await_camera_only_frame() is None
    assert server._camera_frame_cursors == {}


async def test_group_counters_are_independent(server: WebsocketServer) -> None:
    server._app.camera_group_manager.camera_groups = {
        "fast": CameraPayload(id="fast", frame_number=100),
        "slow": CameraPayload(id="slow", frame_number=2),
    }
    first = await server._await_camera_only_frame()
    assert first is not None and first.frame_number == 100
    second = await server._await_camera_only_frame()
    assert second is not None and second.frame_number == 2
    assert await server._await_camera_only_frame() is None
    server._app.camera_group_manager.camera_groups["slow"].frame_number = 3
    third = await server._await_camera_only_frame()
    assert third is not None and third.frame_number == 3
