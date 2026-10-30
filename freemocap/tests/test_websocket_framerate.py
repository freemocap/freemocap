"""Delivery FPS must count delivered frames, not gaps in capture frame IDs."""
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
import cbor2

from freemocap.api.websocket import websocket_server
from freemocap.api.websocket.websocket_server import WebsocketServer


@pytest.mark.asyncio
@pytest.mark.parametrize('capture_step', [1, 2, 4])
async def test_skipped_capture_frames_do_not_inflate_delivery_rate(monkeypatch, capture_step):
    server = WebsocketServer.__new__(WebsocketServer)
    server._server_framerate_calculators = {}
    server._display_framerate_trackers = {}
    server._last_framerate_send_time = 0.0
    server._serializer = type('Serializer', (), {'send_message': AsyncMock()})()
    current_ns = 1_000_000_000
    monkeypatch.setattr(websocket_server, 'time', SimpleNamespace(
        perf_counter_ns=lambda: round(current_ns), perf_counter=lambda: current_ns / 1e9))
    # Deliver 15 FPS, regardless of how many capture IDs are skipped.
    for capture_index in range(0, 5 * capture_step, capture_step):
        server._record_framerate(camera_group_id='cameras', frame_number=capture_index)
        current_ns += 1_000_000_000 / 15
    await server._send_framerate_updates()
    message = cbor2.loads(server._serializer.send_message.call_args.args[0])
    assert message['backend_framerate']['mean_frames_per_second'] == pytest.approx(15)
    current_ns += 1_000_000_000
    server._record_framerate(camera_group_id='cameras', frame_number=5 * capture_step)
    await server._send_framerate_updates()
    assert server._serializer.send_message.await_count == 2
    message = cbor2.loads(server._serializer.send_message.call_args.args[0])
    assert message['backend_framerate']['mean_frame_duration_ms'] == pytest.approx(1000 + 1000 / 15)
