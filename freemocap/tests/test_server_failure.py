"""Fatal application failures stop serving; client disconnects do not."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI, Request, WebSocket
from starlette.websockets import WebSocketDisconnect
from uvicorn import Config, Server

from freemocap.api.websocket import websocket_connect
from freemocap.api.http.app import shutdown
from freemocap.app import app as app_module
from freemocap.app.serve_application import serve_application
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.skeletons.tracked_skeleton_set import build_tracked_skeletons


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.state.global_kill_flag = SimpleNamespace(value=False)
    application.state.fatal_error = None
    return application


async def test_constructor_failure_stops_app_and_rejects_reconnect(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = FileNotFoundError("human_skeleton.yaml")
    constructor = Mock(side_effect=error)
    monkeypatch.setattr(websocket_connect, "WebsocketServer", constructor)
    send = AsyncMock()
    scope = {"type": "websocket", "app": app, "path": "/websocket/connect", "headers": []}
    socket = WebSocket(scope=scope, receive=AsyncMock(return_value={"type": "websocket.connect"}), send=send)
    with pytest.raises(FileNotFoundError, match="human_skeleton.yaml"):
        await websocket_connect.websocket_server_connect(websocket=socket)
    assert app.state.global_kill_flag.value
    assert app.state.fatal_error is error
    assert send.call_args.args[0]["code"] == 1011
    await websocket_connect.websocket_server_connect(
        websocket=WebSocket(scope=scope, receive=AsyncMock(), send=send),
    )
    assert constructor.call_count == 1


async def test_disconnect_does_not_stop_app(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(websocket_connect, "WebsocketServer", Mock(side_effect=WebSocketDisconnect(code=1000)))
    socket = WebSocket(
        scope={"type": "websocket", "app": app, "path": "/websocket/connect", "headers": []},
        receive=AsyncMock(return_value={"type": "websocket.connect"}), send=AsyncMock(),
    )
    await websocket_connect.websocket_server_connect(websocket=socket)
    assert not app.state.global_kill_flag.value
    assert app.state.fatal_error is None


async def test_fatal_flag_drives_uvicorn_exit(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    server = Server(config=Config(app=app))
    server.started = True
    error = FileNotFoundError("human_skeleton.yaml")

    async def serve() -> None:
        app.state.fatal_error = error
        app.state.global_kill_flag.value = True
        while not server.should_exit:
            await asyncio.sleep(0)

    monkeypatch.setattr(server, "serve", serve)
    with pytest.raises(RuntimeError, match="fatal application error") as raised:
        await asyncio.wait_for(serve_application(server=server, app=app), timeout=2)
    assert raised.value.__cause__ is error
    assert server.should_exit


async def test_failed_startup_is_not_success(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    server = Server(config=Config(app=app))
    monkeypatch.setattr(server, "serve", AsyncMock())
    with pytest.raises(RuntimeError, match="startup failed"):
        await serve_application(server=server, app=app)


async def test_missing_resources_fail_startup_and_cleanup(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    application = Mock()
    telemetry_shutdown = Mock()
    error = FileNotFoundError("human_skeleton.yaml")
    monkeypatch.setattr(app_module, "logger", Mock())
    monkeypatch.setattr(app_module, "get_freemocap_app", Mock(return_value=application))
    monkeypatch.setattr(app_module, "build_tracked_skeletons", Mock(side_effect=error))
    monkeypatch.setattr(app_module, "shutdown_telemetry", telemetry_shutdown)
    with pytest.raises(FileNotFoundError, match="human_skeleton.yaml"):
        async with app_module.app_lifespan(app=app):
            pytest.fail("Startup accepted missing resources")
    assert app.state.global_kill_flag.value
    assert app.state.fatal_error is error
    application.close.assert_called_once_with()
    telemetry_shutdown.assert_called_once_with()


def test_installed_default_skeleton_resources_load() -> None:
    assert build_tracked_skeletons(camera_node_config=CameraNodeConfig())


async def test_uvicorn_startup_failure_propagates(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    error = FileNotFoundError("human_skeleton.yaml")
    monkeypatch.setattr(app_module, "logger", Mock())
    monkeypatch.setattr(app_module, "build_tracked_skeletons", Mock(side_effect=error))
    monkeypatch.setattr(app_module, "get_freemocap_app", Mock(return_value=Mock()))
    monkeypatch.setattr(app_module, "shutdown_telemetry", Mock())
    app.router.lifespan_context = app_module.app_lifespan
    server = Server(config=Config(app=app, lifespan="on", log_config=None))
    with pytest.raises(RuntimeError, match="fatal application error") as raised:
        await asyncio.wait_for(serve_application(server=server, app=app), timeout=2)
    assert raised.value.__cause__ is error
    assert not server.started


async def test_shutdown_request_returns_and_stops_server(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutdown, "logger", Mock())
    response = await shutdown.shutdown_server(
        request=Request(scope={"type": "http", "app": app, "path": "/shutdown", "headers": []}),
    )
    assert response.status_code == 200
    assert app.state.global_kill_flag.value
    server = Server(config=Config(app=app))
    server.started = True

    async def serve() -> None:
        while not server.should_exit:
            await asyncio.sleep(0)

    monkeypatch.setattr(server, "serve", serve)
    await asyncio.wait_for(serve_application(server=server, app=app), timeout=2)
    assert server.should_exit
