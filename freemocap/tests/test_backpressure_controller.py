"""F2b — BackpressureController unit tests (pure policy, no asyncio).

SEND while under the window; WAIT when full; ack frees the window; RESET at the
reset threshold; RESET clears ack state; out-of-order ack and reconnect are
no-ops / monotonic (doc 02 § BackpressureController).
"""
from freemocap.api.websocket.backpressure_controller import (
    BackpressureAction,
    BackpressureController,
)


def _controller(window=3, reset=300):
    return BackpressureController(window_size=window, reset_threshold=reset)


def test_send_while_window_open():
    c = _controller()
    assert c.should_send() is BackpressureAction.SEND


def test_wait_when_window_full():
    c = _controller(window=3)
    # send 3 frames (0, 1, 2) → lag = 3 - (-1) = 4? No: lag = last_sent - last_acked.
    # Start: last_sent=-1, last_acked=-1 → unacked 0.
    c.sent(0)
    assert c.should_send() is BackpressureAction.SEND   # lag=1
    c.sent(1)
    assert c.should_send() is BackpressureAction.SEND   # lag=2
    c.sent(2)
    # lag = 2 - (-1) = 3 == window → WAIT
    assert c.unacked_count == 3
    assert c.should_send() is BackpressureAction.WAIT


def test_ack_frees_window():
    c = _controller(window=3)
    for i in range(3):
        c.sent(i)
    assert c.should_send() is BackpressureAction.WAIT
    c.ack(0)
    assert c.unacked_count == 2
    assert c.should_send() is BackpressureAction.SEND


def test_reset_at_threshold():
    c = _controller(window=3, reset=300)
    c.sent(300)  # last_sent=300, last_acked=-1 → lag=301 ≥ 300
    assert c.should_send() is BackpressureAction.RESET


def test_reset_clears_window():
    c = _controller(window=3, reset=300)
    c.sent(500)
    assert c.should_send() is BackpressureAction.RESET
    c.reset()
    assert c.last_sent == -1
    assert c.last_acked == -1
    assert c.unacked_count == 0
    assert c.should_send() is BackpressureAction.SEND


def test_out_of_order_ack_is_monotonic():
    c = _controller(window=3)
    for i in range(3):
        c.sent(i)
    c.ack(2)     # ack ahead
    c.ack(0)     # stale ack — no-op (monotonic)
    assert c.last_acked == 2
    assert c.unacked_count == 0
    assert c.should_send() is BackpressureAction.SEND


def test_reconnect_via_reset():
    c = _controller(window=3)
    for i in range(3):
        c.sent(i)
    c.reset()  # reconnect: drop the window state
    assert c.last_sent == -1
    assert c.last_acked == -1
    assert c.unacked_count == 0
    # fresh sends behave as on connect (first send is always allowed)
    assert c.should_send() is BackpressureAction.SEND


def test_unacked_count_never_negative():
    c = _controller(window=3)
    assert c.unacked_count == 0
    c.ack(5)  # ack with nothing sent — no negative
    assert c.unacked_count == 0
