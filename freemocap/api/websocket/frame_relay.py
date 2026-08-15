"""FrameRelay — the single standard-stream send loop.

Owns the conversion from a per-frame ``FrameContext`` to a ``StreamSample``
(via the producer composition) and its serialization through the
``SendSerializer``. It is the **one** consumer of the pipeline's aggregator
output; the camera images ride the same sample as the ``IMAGE_JPEG`` block.

Flow control is newest-wins: the frame *source* returns the freshest context
available (or ``None`` when nothing new). There is no ack window — a slow
client sees fewer, newer frames.

The frame *source* is an awaitable the supervisor injects
(``wait_for_frame``), so the relay is testable against a synthetic queue while
the real supervisor wires it to the app's aggregator + camera payloads.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from freemocap.api.websocket.send_serializer import SendSerializer  # noqa: TC001 — beartype resolves this in the FrameRelay.__init__ signature at runtime
from freemocap.core.streaming.standard_stream.producers import (
    StreamComposition,
    compose_sample,
)
from freemocap.core.streaming.standard_stream.producers.producer_contexts import (
    FrameContext,
)

logger = logging.getLogger(__name__)

# The source contract: return the next frame context (the frame to compose), or
# None if no new frame is available yet. Raised CancelledError stops the relay;
# any other exception is caught by the supervisor.
FrameSource = Callable[[], Awaitable[FrameContext | None]]


class FrameRelay:
    """Compose + serialize the standard-stream sample path, newest-wins."""

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
        self._composition: StreamComposition | None = None
        self._last_sent_frame_number: int = -1

    async def run(self) -> None:
        """Relay frames until the supervisor's ``should_continue`` goes False.

        The relay owns its exit condition — no reliance on task cancellation
        from ``gather`` (A2).
        """
        while self._should_continue():
            frame_ctx = await self._source()
            if frame_ctx is None:
                await asyncio.sleep(0.01)
                continue
            await self._send_frame(frame_ctx)

    async def _send_frame(self, frame_ctx: FrameContext) -> None:
        if self._composition is None:
            # No schema composed yet — a sample without its schema cannot be
            # decoded. The supervisor composes before starting the relay.
            return
        sample = compose_sample(self._composition, frame_ctx)
        await self._serializer.send_sample(sample.to_bytes())
        self._last_sent_frame_number = frame_ctx.frame_number

    def set_composition(self, composition: StreamComposition) -> None:
        """Swap in a rebuilt composition (data-model change)."""
        self._composition = composition

    @property
    def composition(self) -> StreamComposition | None:
        return self._composition

    @property
    def last_sent_frame_number(self) -> int:
        return self._last_sent_frame_number
