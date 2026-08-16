"""SendSerializer unit tests.

The serializer owns the single-writer lock; these tests use a fake WebSocket to
assert message routing (message -> bytes frame) and the single-writer
serialization without spinning up a real server.
"""
import asyncio

from starlette.websockets import WebSocketState

from freemocap.api.websocket.send_serializer import SendSerializer


class FakeWebSocket:
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


async def test_message_sent_as_bytes_frame():
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    await serializer.send_message(b"\xa1\x01\x02")
    assert ws.sent_bytes == [b"\xa1\x01\x02"]
    assert ws.sent_text == []


async def test_raw_text_sent_as_text_frame():
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    await serializer.send_raw_text("pong")
    assert ws.sent_text == ["pong"]
    assert ws.sent_bytes == []


async def test_sends_are_serialized_through_one_lock():
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    payloads = [bytes([i]) for i in range(50)]
    await asyncio.gather(*[serializer.send_message(p) for p in payloads])
    assert sorted(ws.sent_bytes) == sorted(payloads)


async def test_no_send_when_disconnected():
    ws = FakeWebSocket()
    ws.client_state = WebSocketState.DISCONNECTED
    serializer = SendSerializer(ws)
    await serializer.send_message(b"\x00")
    await serializer.send_raw_text("pong")
    assert ws.sent_bytes == []
    assert ws.sent_text == []
