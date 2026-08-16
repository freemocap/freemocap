"""SendSerializer — the single writer of WebSocket frames.

Enforces the one-writer invariant: the websockets/Starlette transport does not
support concurrent writes on the same connection, so every frame is serialized
through one asyncio.Lock. The serializer owns send_message (one CBOR message
frame) and send_raw_text (protocol ping/pong).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Protocol, runtime_checkable

from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger(__name__)


@runtime_checkable
class _WebSocketTransport(Protocol):
    """The structural subset of WebSocket the serializer drives.

    Kept structural (Protocol, not the concrete class) so the one-writer
    invariant is testable against a fake without a live Starlette connection.
    """

    client_state: WebSocketState

    async def send_text(self, data: str) -> None: ...
    async def send_bytes(self, data: bytes) -> None: ...
    async def close(self, code: int = 1000, reason: str | None = None) -> None: ...


class SendSerializer:
    """One-writer serializer for a single WebSocket connection."""

    def __init__(self, websocket: _WebSocketTransport):
        self.websocket: _WebSocketTransport = websocket
        self._send_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self.websocket.client_state == WebSocketState.CONNECTED

    async def send_message(self, message_bytes: bytes) -> None:
        """Send one CBOR message (a binary frame)."""
        await self.send_raw_bytes(message_bytes)

    async def send_raw_bytes(self, data: bytes) -> None:
        if not self.is_connected:
            return
        async with self._send_lock:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_bytes(data)

    async def send_raw_text(self, text: str) -> None:
        if not self.is_connected:
            return
        async with self._send_lock:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_text(text)
