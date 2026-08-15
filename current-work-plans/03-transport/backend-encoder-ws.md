# Backend Encoder + WebSocket Send-Path

**Describes:** `freemocap/api/websocket/` — `send_serializer.py`, `frame_relay.py`, `websocket_server.py`
— plus the `standard_stream/producers/` package the relay composes samples from.

## What this covers
The **single** send path: one schema on connect (and on every data-model change), then one binary sample
per frame carrying **every block the schema declares — images, overlays, and reconstruction together**.
There is exactly one relay and one consumer of the aggregator output; flow control is newest-wins.

## Architecture

- **One relay, one consumer.** A single relay loop is the sole consumer of the pipeline's
  `aggregation_output_subscription`. Each tick it builds a `FrameContext`, composes one sample from the
  active producers, and sends it. There is **no second send loop** — the camera images ride the same
  sample as a channel group (`IMAGE_JPEG`), not a separate stream.

  ```
  FrameContext = { frame_number, timestamp, aggregator_output | None, image_payload_bytes | None, standard_human }
  ```

  In a live realtime pipeline the relay drains the aggregator output (frame number + pose) and fetches the
  matching image bytes by frame number; in camera-only mode there is no aggregator output, so the sample
  carries only the `ImageProducer`'s block. Same loop, same sample type — the difference is which
  producers are active, i.e. the schema (see
  [../01-data-model/stream-contract.md](../01-data-model/stream-contract.md)).

- **Producer-composed schema + sample.** The relay does not hand-build blocks. It asks the active
  producers to `fill(ctx)`; the schema is composed from the same producers' `schema_groups` +
  `schema_metadata`. Adding a data type is adding a producer — the relay is unchanged.

- **Newest-wins, drop-stale — no ack window.** The relay always sends the freshest frame and drops
  anything the client can't keep up with (the aggregator source is newest-wins: `if_newer_than=last_sent`,
  take the max). There is **no `BackpressureController`** and no send-window; a slow client simply sees
  fewer, newer frames. This is the correct model for a realtime "show me the latest" view and removes the
  send-3-then-wait sawtooth that decoupled overlays from images.

- **`SendSerializer` — the single writer.** One `asyncio.Lock` serializes every write (schema JSON +
  binary samples); the transport cannot take concurrent writes. Because the lock serializes
  rebuild→send-schema→send-sample, a sample never precedes the schema it conforms to.

- **`WebsocketServer` — the supervisor.** Builds the schema on connect, then rebuilds + resends it on
  **any config change** — the rebuild is event-driven off the existing pubsub network: the supervisor
  subscribes to freemocap's `PipelineConfigUpdateTopic` (per pipeline) and skellycam's
  `UPDATE_CAMERA_SETTINGS` / `EXTRACTED_CONFIG` (per camera group), and a message on any of them is a
  full schema rebuild. The composite **schema signature** remains as the backstop for changes that
  don't ride a config topic (pipeline start/stop) and for configs mid-application. Runs the relay +
  log relay + app-state sender + inbound client-message handler under one `gather`. The inbound
  `frameAcknowledgment` is retained **only** to carry `displayImageSizes` (which drive SkellyCam's
  downscaling); it has **no flow-control role**.

## Image bytes (no SkellyCam changes)
The relay fetches images from the existing SkellyCam `camera_group` API only —
`pipeline.camera_group.get_frontend_payload_by_frame_number(frame_number)` in a live pipeline (paired with
the aggregator output's frame number), `camera_group_manager.get_latest_frontend_payloads()` in
camera-only mode. The returned multi-camera payload is embedded as one opaque `IMAGE_JPEG` block; the
consumer's existing frame decoder splits it per camera. Reuse the existing reusable-bytearray buffer so a
multi-MB image block is not reallocated per frame.

## Reconciliation notes
"Standard-stream sample," not "binary keypoints." Images are a **channel group in the sample**, not a
separate stream. Flow control is newest-wins (no ack window). The wire framing lives in
[standard-stream-protocol.md](standard-stream-protocol.md); the shapes in
[../01-data-model/stream-contract.md](../01-data-model/stream-contract.md).
