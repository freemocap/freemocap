"""FrameRelay — the single frame-message send loop.

Owns the conversion from a per-frame FrameContext to a self-describing
FrameMessage (via the message composition) and its CBOR serialization through
the SendSerializer. It is the ONE consumer of the pipeline's aggregator output;
the camera images ride the frame message's image field.

Flow control is newest-wins: the frame source returns the freshest context
available (or None when nothing new). There is no ack window — a slow client
sees fewer, newer frames.

The frame source is an awaitable the supervisor injects (wait_for_frame), so
the relay is testable against a synthetic queue while the real supervisor wires
it to the app's aggregator + camera payloads.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from freemocap.api.websocket.send_serializer import SendSerializer  # noqa: TC001
from freemocap.core.streaming.message_composer import MessageComposition  # noqa: TC001
from freemocap.core.streaming.message_model import encode_message
from freemocap.core.streaming.producers.producer_contexts import FrameContext  # noqa: TC001

logger = logging.getLogger(__name__)

FrameSource = Callable[[], Awaitable[FrameContext | None]]


class FrameRelay:
    """Compose + serialize the frame-message path, newest-wins."""

    def __init__(
        self,
        *,
        serializer: SendSerializer,
        source: FrameSource,
        should_continue: Callable[[], bool],
    ):
        self._serializer = serializer
        self._source = source
        self._should_continue = should_continue
        self._composition: MessageComposition | None = None
        self._last_sent_frame_number: int = -1

    async def run(self) -> None:
        """Relay frames until the supervisor's should_continue goes False."""
        while self._should_continue():
            frame_ctx = await self._source()
            if frame_ctx is None:
                await asyncio.sleep(0.01)
                continue
            await self._send_frame(frame_ctx)

    async def _send_frame(self, frame_ctx: FrameContext) -> None:
        if self._composition is None:
            return
        message = self._composition.compose_frame_message(frame_ctx)
        await self._serializer.send_message(encode_message(message))
        self._last_sent_frame_number = frame_ctx.frame_number

    def set_composition(self, composition: MessageComposition) -> None:
        """Swap in a rebuilt composition (data-model change)."""
        self._composition = composition

    @property
    def composition(self) -> MessageComposition | None:
        return self._composition

    @property
    def last_sent_frame_number(self) -> int:
        return self._last_sent_frame_number
