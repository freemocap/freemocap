"""BackpressureController — the WS send-path ack-window policy.

Pure policy: no asyncio, no I/O, no WebSocket coupling. The relay asks
``should_send()`` before encoding/sending the next frame; the client ack
handler calls ``ack()``; the relay records ``sent()`` after a frame goes out.

States (per doc 02 § BackpressureController)::

    SEND   — in-flight window has room; send the next frame
    WAIT   — window full; hold frames until an ack frees a slot
    RESET  — frontend hopelessly behind; clear the window state and proceed

The window is counted in unacknowledged *frames*: ``last_sent - last_acked``.
``window_size`` frames may be in flight before the relay must wait.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class BackpressureAction(Enum):
    SEND = auto()     # room in the window — send the next frame
    WAIT = auto()     # window full — hold until an ack
    RESET = auto()    # frontend >= reset_threshold behind — clear and proceed


@dataclass
class BackpressureController:
    """Ack-window policy. Stateless aside from the two counters."""

    window_size: int = 3          # max unacknowledged frames in flight
    reset_threshold: int = 300    # frames behind → RESET rather than stall

    _last_sent: int = -1
    _last_acked: int = -1

    @property
    def unacked_count(self) -> int:
        """Frames sent but not yet acknowledged (0 when nothing outstanding)."""
        if self._last_sent < 0:
            return 0
        return max(0, self._last_sent - self._last_acked)

    @property
    def last_sent(self) -> int:
        return self._last_sent

    @property
    def last_acked(self) -> int:
        return self._last_acked

    def ack(self, frame_number: int) -> None:
        """Record a client ack. Out-of-order acks are a no-op (monotonic)."""
        self._last_acked = max(self._last_acked, frame_number)

    def sent(self, frame_number: int) -> None:
        self._last_sent = frame_number

    def should_send(self) -> BackpressureAction:
        lag = self.unacked_count
        if lag >= self.reset_threshold:
            return BackpressureAction.RESET
        if lag >= self.window_size:
            return BackpressureAction.WAIT
        return BackpressureAction.SEND

    def reset(self) -> None:
        """Clear the window state (the relay's RESET branch)."""
        self._last_sent = -1
        self._last_acked = -1
