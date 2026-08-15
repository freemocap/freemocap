"""SendSerializer — the single writer of WebSocket frames.

Enforces the one-writer invariant: the ``websockets``/Starlette transport
does not support concurrent writes on the same connection, so every frame
(text JSON and binary bytes) is serialized through one ``asyncio.Lock``.

Owns:
  * ``_send_lock`` — the serialization primitive (the single-writer invariant)
  * ``send_schema(bytes)`` — schema JSON, sent on connect / schema change
  * ``send_sample(bytes)`` — one standard-stream sample frame
  * ``send_json(obj)`` — any msgspec-encodable object (settings, logs, …)

JSON encoding is msgspec-based (a Pydantic/dataclass/numpy-aware hook) so the
push is cheap and consistent with the rest of the send path.
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import Protocol, runtime_checkable

import msgspec
import numpy as np
from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger(__name__)

_send_log_count = 0  # TEMP DEBUG — remove


@runtime_checkable
class _WebSocketTransport(Protocol):
    """The structural subset of ``WebSocket`` the serializer drives.

    Kept structural (Protocol, not the concrete class) so the one-writer
    invariant is testable against a fake without a live Starlette connection.
    """

    client_state: WebSocketState

    async def send_text(self, data: str) -> None: ...
    async def send_bytes(self, data: bytes) -> None: ...
    async def close(self, code: int = 1000, reason: str | None = None) -> None: ...


def _msgspec_enc_hook(obj: object) -> object:
    """Fallback encoder for types msgspec doesn't natively handle."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dataclass_fields__"):
        return dataclasses.asdict(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Cannot encode object of type {type(obj).__name__}")


_ws_json_encoder = msgspec.json.Encoder(enc_hook=_msgspec_enc_hook)


class SendSerializer:
    """One-writer serializer for a single WebSocket connection."""

    def __init__(self, websocket: _WebSocketTransport):
        self.websocket: _WebSocketTransport = websocket
        self._send_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self.websocket.client_state == WebSocketState.CONNECTED

    async def send_schema_json(self, schema_bytes: bytes) -> None:
        """Send the schema JSON (a single text frame) on connect / change."""
        await self.send_raw_text(schema_bytes.decode("utf-8"))

    async def send_sample(self, sample_bytes: bytes) -> None:
        """Send one standard-stream sample (binary frame)."""
        # TEMP DEBUG — remove
        global _send_log_count
        _send_log_count += 1
        if _send_log_count <= 5 or _send_log_count % 100 == 0:
            logger.info(
                f"[TEMP] serializer send_sample #{_send_log_count} "
                f"len={len(sample_bytes)} first_byte={sample_bytes[0] if sample_bytes else None}"
            )
        await self.send_raw_bytes(sample_bytes)

    async def send_json(self, data: object) -> None:
        """Encode any msgspec-compatible object and send as a text frame."""
        await self.send_raw_text(_ws_json_encoder.encode(data).decode("utf-8"))

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
