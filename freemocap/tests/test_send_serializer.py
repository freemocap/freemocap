"""F2b — SendSerializer unit tests.

The serializer owns the single-writer lock; these tests use a fake WebSocket
to assert schema/sample routing (schema → text frame, sample → bytes frame)
and the single-writer serialization without spinning up a real server.
"""
import asyncio

import pytest
from starlette.websockets import WebSocketState

from freemocap.api.websocket.send_serializer import SendSerializer


class FakeWebSocket:
    """Minimal Starlette-WebSocket-shaped fake recording outgoing frames."""

    def __init__(self):
        self.client_state = WebSocketState.CONNECTED
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.client_state = WebSocketState.DISCONNECTED


async def test_schema_json_sent_as_text_frame():
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    await serializer.send_schema_json(b'{"stream_id": "x"}')
    assert ws.sent_text == ['{"stream_id": "x"}']
    assert ws.sent_bytes == []


async def test_sample_sent_as_bytes_frame():
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    await serializer.send_sample(b"\x0a\x00\x00\x00")
    assert ws.sent_bytes == [b"\x0a\x00\x00\x00"]
    assert ws.sent_text == []


async def test_send_json_uses_msgspec_encoder():
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    await serializer.send_json({"message_type": "app_state", "state": {}})
    assert '"message_type"' in ws.sent_text[0]
    assert '"app_state"' in ws.sent_text[0]


async def test_sends_are_serialized_through_one_lock():
    # Structural single-writer check: N concurrent sends must not interleave —
    # the serializer funnels them through the same asyncio.Lock. We assert the
    # outgoing frame set is complete and un-corrupted.
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    payloads = [bytes([i]) for i in range(50)]
    await asyncio.gather(*[serializer.send_sample(p) for p in payloads])
    assert sorted(ws.sent_bytes) == sorted(payloads)


async def test_no_send_when_disconnected():
    ws = FakeWebSocket()
    ws.client_state = WebSocketState.DISCONNECTED
    serializer = SendSerializer(ws)
    await serializer.send_sample(b"\x00")
    await serializer.send_schema_json(b"{}")
    assert ws.sent_bytes == []
    assert ws.sent_text == []
