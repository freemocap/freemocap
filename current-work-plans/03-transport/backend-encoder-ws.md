# Backend Encoder + WebSocket Send-Path

**Describes:** `freemocap/api/websocket/` — `send_serializer.py`, `frame_relay.py`,
`backpressure_controller.py`, `websocket_server.py`.
**Salvage:** [`archive/streaming-compatibility-specs/06-backend-refactor-and-cleanup.md`](../archive/streaming-compatibility-specs/06-backend-refactor-and-cleanup.md),
[`archive/phase-1-work-plans/02-backend-encoder-and-ws-reshape.md`](../archive/phase-1-work-plans/02-backend-encoder-and-ws-reshape.md).

## What this covers
The reshaped send path that replaced the legacy binary-keypoints protocol (D36): schema once, then binary
standard-stream **samples**, ack-window gated — composed with the separate image relay, log relay, and
client-message handler in one per-connection supervisor.

## Architecture (committed code)
- **`SendSerializer`** — the single writer. One `asyncio.Lock` serializes every frame (text + bytes);
  the `websockets`/Starlette transport can't take concurrent writes. Guards connection state around the lock.
- **`FrameRelay`** — the standard-stream middle: aggregator output → `StreamSample` → serialize, gated by
  the backpressure controller. Frame source is injected (testable against a synthetic queue).
- **`BackpressureController`** — pure ack-window policy (`SEND`/`WAIT`/`RESET`), no I/O.
- **`WebsocketServer`** — the supervisor: builds the schema on connect, resends it on camera-topology or
  material length change, runs the five tasks under one `gather`, routes client acks to the relay.

## Known defects (the fix queue)
- **A2 (open)** — `FrameRelay.run()` loops `while True` while the other tasks honour `should_continue`;
  the relay can't self-terminate on disconnect. Give it a stop signal.
- **B1 (open)** — the ack window counts frame-number deltas but treats them as in-flight count;
  incompatible with the relay's newest-wins skipping. Count actual in-flight sends.
- **B2 (done)** — the schema re-send is already gated: rebuilt only on camera-set change or when
  `lengths_differ_materially` fires (any segment > 1.0 mm); converged estimators stop re-sending.

## Reconciliation notes
"Standard-stream sample," not "binary keypoints." Image data stays a **separate** JPEG stream keyed by
frame number (never gated by the sample ack window).
