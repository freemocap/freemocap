"""BackpressureController — the WS send-path ack-window policy.

Pure policy: no asyncio, no I/O, no WebSocket coupling. The relay asks
``should_send()`` before encoding/sending the next frame; the client ack
handler calls ``ack()``; the relay records ``sent()`` after a frame goes out.

States (per doc 02 § BackpressureController)::

    SEND   — in-flight window has room; send the next frame
    WAIT   — window full; hold frames until an ack frees a slot
    RESET  — frontend hopelessly behind; clear the window state and proceed

Two different quantities, on purpose:

- The **window** (WAIT) counts *actual in-flight sends* — a monotonically
  increasing sent counter minus the acked counter (B1). Frame numbers jump
  under the relay's newest-wins skipping, so a frame-number delta would
  overcount the window and stall a healthy client.
- The **reset trigger** is the *frame-number distance* between the newest send
  and the newest ack — how many frames of stream progress the client has not
  acknowledged. That is the honest "hopelessly behind" signal: skips alone
  never fire it (they are a few frames), a frozen client fires it even though
  the send counter stays capped at the window.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto


class BackpressureAction(Enum):
    SEND = auto()     # room in the window — send the next frame
    WAIT = auto()     # window full — hold until an ack
    RESET = auto()    # frontend >= reset_threshold behind — clear and proceed


@dataclass
class BackpressureController:
    """Ack-window policy: send-counting for the window, frame-distance for RESET."""

    window_size: int = 3          # max unacknowledged sends in flight
    reset_threshold: int = 300    # frames behind → RESET rather than stall

    _last_sent: int = -1
    _last_acked: int = -1
    _sent_count: int = 0
    _acked_count: int = 0
    # Sent frame numbers not yet acknowledged, oldest first (window-bounded in
    # practice; RESET clears it before it can grow).
    _in_flight: deque[int] = field(default_factory=deque)

    @property
    def unacked_count(self) -> int:
        """Sends actually in flight (acked sends subtracted — never a frame delta)."""
        return self._sent_count - self._acked_count

    @property
    def last_sent(self) -> int:
        return self._last_sent

    @property
    def last_acked(self) -> int:
        return self._last_acked

    def ack(self, frame_number: int) -> None:
        """Record a client ack: every send at or below ``frame_number`` is acked.

        Only frames actually sent are credited — a frame-number gap from
        newest-wins skipping never marks unsent frames acked. Out-of-order /
        repeated acks are no-ops (the in-flight queue is popped in send order).
        """
        self._last_acked = max(self._last_acked, frame_number)
        while self._in_flight and self._in_flight[0] <= frame_number:
            self._in_flight.popleft()
            self._acked_count += 1

    def sent(self, frame_number: int) -> None:
        self._last_sent = frame_number
        self._in_flight.append(frame_number)
        self._sent_count += 1

    def should_send(self) -> BackpressureAction:
        if self._last_sent >= 0:
            lag = self._last_sent - self._last_acked
            if lag >= self.reset_threshold:
                return BackpressureAction.RESET
        if self.unacked_count >= self.window_size:
            return BackpressureAction.WAIT
        return BackpressureAction.SEND

    def reset(self) -> None:
        """Clear the window state (the relay's RESET branch / reconnect)."""
        self._last_sent = -1
        self._last_acked = -1
        self._sent_count = 0
        self._acked_count = 0
        self._in_flight.clear()
