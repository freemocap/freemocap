"""Exercise the installed ASGI transport, including delayed loss notification."""

import asyncio
import logging
import socket as socket_module
from queue import Queue
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState
from uvicorn import Config, Server
from uvicorn.server import ServerState
from websockets.protocol import State
from websockets.asyncio.client import connect

from freemocap.api.websocket import websocket_server
from freemocap.api.websocket import websocket_connect
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistry
from freemocap.api.websocket.closing_aware_protocol import ClosingAwareWebSocketProtocol
from freemocap.api.websocket.websocket_server import WebsocketServer
from freemocap.api.websocket.send_serializer import SendSerializer


class RecordingTransport(asyncio.Transport):
    def __init__(self):
        self.closing = False
        self.writes = 0

    def is_closing(self):
        return self.closing

    def write(self, data):
        self.writes += 1
        if self.closing:
            # Windows logs and returns here; it does not raise to the caller.
            logging.getLogger("asyncio").warning("socket.send() raised exception.")


def connection():
    protocol = ClosingAwareWebSocketProtocol(
        config=Config(app=Mock(), factory=True, log_config=None, ws_ping_interval=None),
        server_state=ServerState(), app_state={},
    )
    transport = RecordingTransport()
    protocol.transport = transport
    protocol.connections.add(protocol)
    protocol.handshake_complete = True
    protocol.conn.state = State.OPEN
    socket = WebSocket(
        scope={"type": "websocket"}, receive=protocol.receive, send=protocol.send,
    )
    socket.client_state = socket.application_state = WebSocketState.CONNECTED
    return protocol, transport, socket


@pytest.mark.parametrize("text", [False, True])
async def test_closing_transport_rejects_send_before_loss_callback(text):
    protocol, transport, socket = connection()
    transport.closing = True
    assert not protocol.disconnected
    with pytest.raises(WebSocketDisconnect):
        if text:
            await socket.send_text("pong")
        else:
            await socket.send_bytes(b"frame")
    assert transport.writes == 0


async def test_close_while_sender_waits_for_backpressure():
    protocol, transport, socket = connection()
    protocol.writable.clear()
    task = asyncio.create_task(socket.send_bytes(b"frame"))
    await asyncio.sleep(0)
    transport.closing = True
    protocol.writable.set()
    with pytest.raises(WebSocketDisconnect):
        await task
    assert transport.writes == 0


async def test_waiting_senders_do_not_write_after_first_send_disconnects():
    protocol, transport, socket = connection()
    serializer = SendSerializer(socket)
    protocol.writable.clear()
    first = asyncio.create_task(serializer.send_message(b"app state"))
    await asyncio.sleep(0)
    second = asyncio.create_task(serializer.send_message(b"progress"))
    third = asyncio.create_task(serializer.send_raw_text("pong"))
    await asyncio.sleep(0)
    transport.closing = True
    protocol.writable.set()
    results = await asyncio.gather(first, second, third, return_exceptions=True)
    assert isinstance(results[0], WebSocketDisconnect)
    assert results[1:] == [None, None]
    assert socket.client_state == WebSocketState.CONNECTED
    assert socket.application_state == WebSocketState.DISCONNECTED
    assert not serializer.is_connected
    assert transport.writes == 0


async def test_startup_senders_disconnect_without_fatal_server_shutdown(monkeypatch):
    _, transport, socket = connection()
    transport.closing = True
    app = FastAPI()
    app.state.global_kill_flag = SimpleNamespace(value=False)
    app.state.fatal_error = None
    socket.scope.update(app=app, path="/websocket/connect", headers=[])
    # connection() already completed the handshake; exercise the actual route
    # and all sender tasks with the first application send failing.
    monkeypatch.setattr(socket, "accept", AsyncMock())
    server = WebsocketServer.__new__(WebsocketServer)
    server.websocket = socket
    server._global_kill_flag = app.state.global_kill_flag
    server._websocket_should_continue = True
    server._serializer = SendSerializer(socket)
    server.ws_tasks = []
    server._app = SimpleNamespace(
        to_state_dict=lambda: {},
        posthoc_pipeline_manager=SimpleNamespace(task_snapshot=TaskRegistry().snapshot),
    )

    async def idle():
        await asyncio.Event().wait()

    server._relay = SimpleNamespace(run=idle)
    monkeypatch.setattr(websocket_connect, "WebsocketServer", lambda **kwargs: server)
    monkeypatch.setattr(websocket_server, "get_websocket_log_queue", lambda: Queue())
    await asyncio.wait_for(websocket_connect.websocket_server_connect(socket), timeout=1)
    assert app.state.fatal_error is None
    assert not app.state.global_kill_flag.value
    assert all(task.done() for task in server.ws_tasks)
    assert transport.writes == 0


@pytest.mark.parametrize("record", [
    {"name": "application", "levelno": logging.WARNING, "message": "busy"},
    {"name": "application", "levelno": logging.DEBUG},
    None,
])
async def test_busy_log_relay_allows_disconnect_to_run(monkeypatch, record):
    protocol, transport, socket = connection()
    server = WebsocketServer.__new__(WebsocketServer)
    server.websocket = socket
    server._global_kill_flag = SimpleNamespace(value=False)
    server._websocket_should_continue = True
    server._serializer = SendSerializer(socket)
    queue = Queue()
    # A bounded backlog makes failure deterministic without hanging the test.
    for _ in range(100):
        queue.put_nowait(record)
    monkeypatch.setattr(websocket_server, "get_websocket_log_queue", lambda: queue)
    relay = asyncio.create_task(server._logs_relay(ws_log_level=logging.WARNING))

    def disconnect():
        transport.closing = True
        protocol.connection_lost(ConnectionResetError())

    asyncio.get_running_loop().call_soon(disconnect)
    message = await asyncio.wait_for(socket.receive(), timeout=1)
    assert message["type"] == "websocket.disconnect"
    await asyncio.wait_for(relay, timeout=1)
    assert queue.qsize() > 0, "The relay drained its backlog before allowing disconnect"


async def test_busy_log_relay_can_be_cancelled(monkeypatch):
    _, _, socket = connection()
    server = WebsocketServer.__new__(WebsocketServer)
    server.websocket = socket
    server._global_kill_flag = SimpleNamespace(value=False)
    server._websocket_should_continue = True
    server._serializer = SendSerializer(socket)
    queue = Queue()
    for _ in range(100):
        queue.put_nowait({"name": "application", "levelno": logging.WARNING})
    monkeypatch.setattr(websocket_server, "get_websocket_log_queue", lambda: queue)
    relay = asyncio.create_task(server._logs_relay())
    asyncio.get_running_loop().call_soon(relay.cancel)
    await asyncio.wait_for(relay, timeout=1)
    assert queue.qsize() > 0, "Cancellation was starved until the backlog was empty"


async def test_send_failure_joins_connection_tasks(monkeypatch):
    _, transport, socket = connection()
    transport.closing = True
    server = WebsocketServer.__new__(WebsocketServer)
    server.websocket = socket
    server._global_kill_flag = SimpleNamespace(value=False)
    server._websocket_should_continue = True
    server._serializer = SendSerializer(socket)
    server.ws_tasks = []

    async def idle():
        await asyncio.Event().wait()

    server._relay = SimpleNamespace(run=idle)
    monkeypatch.setattr(server, "_app_state_sender", idle)
    monkeypatch.setattr(server, "_posthoc_progress_sender", idle)
    queue = Queue()
    queue.put_nowait({"name": "application", "levelno": logging.WARNING})
    monkeypatch.setattr(websocket_server, "get_websocket_log_queue", lambda: queue)
    async with server:
        await asyncio.wait_for(server.run(), timeout=1)
    assert all(task.done() for task in server.ws_tasks)
    assert not server._global_kill_flag.value
    assert transport.writes == 0


async def test_real_socket_exchange_disconnect_reconnect_and_shutdown():
    disconnected = asyncio.Event()

    async def app(scope, receive, send):
        socket = WebSocket(scope, receive, send)
        await socket.accept()
        try:
            while True:
                data = await socket.receive_bytes()
                await socket.send_bytes(data)
        except WebSocketDisconnect:
            disconnected.set()

    listener = socket_module.socket()
    listener.bind(("127.0.0.1", 0))
    config = Config(
        app=app, ws=ClosingAwareWebSocketProtocol, lifespan="off",
        log_config=None, timeout_graceful_shutdown=1,
    )
    server = Server(config)
    serving = asyncio.create_task(server.serve(sockets=[listener]))

    async def wait_until_started():
        while not server.started:
            if serving.done():
                await serving
                raise AssertionError("Server stopped before startup")
            await asyncio.sleep(0.01)

    try:
        await asyncio.wait_for(wait_until_started(), timeout=3)
        url = f"ws://127.0.0.1:{listener.getsockname()[1]}/"
        for abrupt in (True, False):
            disconnected.clear()
            async with connect(url) as client:
                await client.send(b"frame")
                assert await asyncio.wait_for(client.recv(), timeout=1) == b"frame"
                assert all(
                    isinstance(connection, ClosingAwareWebSocketProtocol)
                    for connection in server.server_state.connections
                )
                if abrupt:
                    client.transport.abort()
                else:
                    await client.close()
                await asyncio.wait_for(disconnected.wait(), timeout=1)
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(serving, timeout=3)
        finally:
            listener.close()
    assert not server.server_state.tasks
