"""FrameRelay — the async middle of the standard-stream send path.

Owns the conversion from the aggregator's per-frame output message to a
``StreamSample`` (F2a's ``from_aggregator_output``) and its serialization via
the ``SendSerializer``, gated by the ``BackpressureController``. It does not
frame the wire protocol — the sample codec does — and it does not own the
WebSocket (the serializer does). It is the one place that asks "can I send?"
before encoding.

The frame *source* is an awaitable the supervisor injects (``wait_for_frame``),
so the relay is testable against a synthetic queue while the real supervisor
wires it to ``FreemocapApplication.wait_for_realtime_result``.

Image data is deliberately NOT this relay's job — images stay a separate
JPEG-bytearray stream in the supervisor (see doc 02 § Goal 4).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from freemocap.api.websocket.backpressure_controller import (
    BackpressureAction,
    BackpressureController,
)
from freemocap.api.websocket.send_serializer import SendSerializer  # noqa: TC001 — beartype resolves this in the FrameRelay.__init__ signature at runtime
from freemocap.core.streaming.standard_stream import (
    StreamSample,
    StreamSchema,
    encode_schema,
)
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage  # noqa: TC001

logger = logging.getLogger(__name__)

# The source contract: return the next aggregator output message (the frame to
# encode), or None if no new frame is available yet. Raised CancelledError stops
# the relay; any other exception is caught by the supervisor.
FrameSource = Callable[[], Awaitable[AggregationNodeOutputMessage | None]]


class FrameRelay:
    """Encode + serialize the standard-stream sample path, ack-window gated."""

    def __init__(
        self,
        *,
        serializer: SendSerializer,
        backpressure: BackpressureController,
        schema: StreamSchema,
        standard_human,
        source: FrameSource,
        should_continue: Callable[[], bool],
    ):
        self._serializer = serializer
        self._backpressure = backpressure
        self._schema = schema
        self._standard_human = standard_human
        self._source = source
        self._should_continue = should_continue
        self._last_sent_frame_number: int = -1

    async def run(self) -> None:
        """Relay frames until the supervisor's ``should_continue`` goes False.

        The relay owns its exit condition — no reliance on task cancellation
        from ``gather`` (A2).
        """
        while self._should_continue():
            action = self._backpressure.should_send()
            if action is BackpressureAction.RESET:
                logger.warning("backpressure RESET — clearing ack window")
                self._backpressure.reset()
            elif action is BackpressureAction.WAIT:
                # Window full — yield and let an ack free a slot.
                await asyncio.sleep(0.01)
                continue

            message = await self._source()
            if message is None:
                await asyncio.sleep(0.01)
                continue

            await self._send_frame(message)

    async def _send_frame(self, message: AggregationNodeOutputMessage) -> None:
        sample = StreamSample.from_aggregator_output(
            message=message,
            schema=self._schema,
            standard_human=self._standard_human,
        )
        await self._serializer.send_sample(sample.to_bytes())
        self._last_sent_frame_number = message.frame_number
        self._backpressure.sent(message.frame_number)

    def ack(self, frame_number: int) -> None:
        """Record a client ack (called by the supervisor's inbound handler)."""
        self._backpressure.ack(frame_number)

    def set_schema(self, schema: StreamSchema) -> None:
        """Swap in a rebuilt schema (camera-topology change)."""
        self._schema = schema

    @property
    def last_sent_frame_number(self) -> int:
        return self._last_sent_frame_number


def schema_bytes(schema: StreamSchema) -> bytes:
    """The schema JSON sent on connect / change."""
    return encode_schema(schema)


# Any single segment differing by more than this many mm triggers a schema
# re-send. Chosen above the estimator's frame-to-frame jitter so converged,
# stable estimates stop re-sending, but well below a visible change in rendered
# bone span (~1 mm is invisible to the eye and every segment would need to move
# in unison to shift the rendered figure).
LENGTH_CHANGE_THRESHOLD_MM = 1.0


def lengths_differ_materially(
    old: dict[str, float] | None,
    new: dict[str, float],
) -> bool:
    """True when the measured lengths have changed enough to justify a re-send.

    First arrival (``old is None``) always fires — the frontend has no lengths
    yet and must receive the initial mapping. Thereafter the predicate fires
    only when any single segment length differs by more than
    ``LENGTH_CHANGE_THRESHOLD_MM`` (1.0 mm). Because the estimators converge
    then stabilize, the per-segment change shrinks below the threshold and
    re-sends stop.
    """
    if old is None:
        return True
    for name, length in new.items():
        prev = old.get(name)
        if prev is None or abs(float(length) - prev) > LENGTH_CHANGE_THRESHOLD_MM:
            return True
    return False
