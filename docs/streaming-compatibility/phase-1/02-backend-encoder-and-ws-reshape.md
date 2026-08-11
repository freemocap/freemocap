# WS-2 — Backend Encoder + WebSocket Send-Path Reshape

> Build order: after WS-1 (contract) + WS-3 (frame extensions). Realizes
> [06](../06-backend-refactor-and-cleanup.md), [09](../09-standard-stream-protocol.md).
> **Status: plan for agreement — no code until agreed.**

## Goal

Produce the standard stream (schema once + samples per frame) from the canonical frame using WS-1's codecs, and
wire it into the WebSocket send path — decomposing today's monolithic send path into focused components
([06](../06-backend-refactor-and-cleanup.md)). **Image data stays a separate stream** (linked by frame number).

## Files (evolve)

- `freemocap/api/websocket/websocket_server.py` — the per-connection `WebsocketServer` send path.
- `freemocap/core/viz/frontend_keypoints_serializer.py` — `build_keypoints_payload` → **replaced** by WS-1's
  `encode_sample`.
- `freemocap/core/viz/frontend_payload.py` — `FrontendPayload` numeric bits → a `SCALARS` block; **per-camera
  2D overlays → `OVERLAY_2D` blocks in the stream**.
- `freemocap/api/websocket/tracker_schema_message.py` — `_send_tracker_schemas` → send `stream_schema`.
- `freemocap/core/pipeline/realtime/realtime_pipeline.py` / `realtime_pipeline_manager.py` —
  `get_latest_frontend_payload`.
- `freemocap/app/freemocap_application.py` — `get_latest_frontend_payloads`.

## The work

1. **Standard-stream encoder** — canonical frame → `stream_schema` (on connect/change) + `stream_sample` (per
   frame), via WS-1 codecs. The **shared** component the LSL route reuses later.
2. **Send-path decomposition** ([06](../06-backend-refactor-and-cleanup.md)): send-serializer (the `_send_lock`
   one-writer), frame-relay (samples), backpressure/ack controller (policy object, no I/O), framerate reporter,
   log relay, app-state sender, client-message handler. `WebsocketServer` → thin supervisor.
3. **Camera images stay separate; 2D overlay *data* goes in the stream.** The image relay
   (`_frontend_image_relay` pixel frames) stays its own channel, linked by frame number. But the per-camera 2D
   **overlay coordinates** (`OVERLAY_2D`) travel *in* the standard stream — matching the 3D data, 2D-only.
4. **Schema lifecycle** — send `stream_schema` on connect + on tracker/convention change (subsumes
   `_send_tracker_schemas`).

## Task checklist

1. [ ] Standard-stream encoder (frame → schema/sample) on WS-1.
2. [ ] Extract send-serializer + backpressure controller (policy) + framerate reporter.
3. [ ] Frame-relay sends samples; schema on connect/change.
4. [ ] Keep the image relay separate; link by frame number.
5. [ ] Retire `build_keypoints_payload` / `FrontendPayload`-numeric / `TrackerSchemasMessage`.
6. [ ] `WebsocketServer` → thin supervisor.

## Tests

- Encoder: a canonical frame → schema+sample matching the WS-1 golden.
- Backpressure controller unit tests (synthetic ack-lag).
- Integration: connect → schema → samples flow; the image path is unaffected.

## Not in scope

UI decode (WS-4); rotation *values* (WS-5); LSL transport (Phase 2).

## Micro-decisions to confirm

- Where the encoder lives (shared location for the WS relay + the future LSL route).
- How much of the [06](../06-backend-refactor-and-cleanup.md) decomposition lands now vs. incrementally.
