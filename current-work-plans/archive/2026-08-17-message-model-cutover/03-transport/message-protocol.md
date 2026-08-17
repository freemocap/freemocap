# The Message Protocol (self-describing; no schema, no samples)

**Describes:** the wire behavior — one WebSocket carrying a stream of **self-describing messages**. There
is no schema and no samples. Every message is typed, versioned, and carries everything needed to decode
(and, for a frame, render) it, so a client holds no reconstruction state and can never decode against a
stale descriptor.

## Why

The old schema-then-samples wire made the client's ability to decode depend on a separately-held
descriptor — a **stateful coupling**: the descriptor and the data can fall out of sync *silently*, because
nothing in a sample says which descriptor it assumes. Two processes that start, stop, and reconnect
independently (browser + server) make that desync a permanent liability. Self-describing messages remove
the coupling: any message can be interpreted on its own terms. The second-order win is surface-area
reduction — no held descriptor, no change-detection, no resend lifecycle, no schema-before-samples
ordering guarantee; just the single invariant a one-writer lock already gives us (send order).

CBOR (not JSON / MessagePack / Protobuf) because it is the standards-track self-describing *binary* format:
native byte strings carry the JPEG payload and the packed Float32 arrays directly (no base64, no
typed-array tag ambiguity). With four cameras of JPEG per frame the non-image payload is ~5%, so the
metadata channel is optimized for robustness and clarity, not bytes.

## The model

The stream is a sequence of **messages**. Each message declares a **kind** (which handler consumes it) and
a **shape version**, then its payload. Kinds differ only in cadence (frame every frame; the rest on
change/emit) and consumption (frames emit to renderers; the rest replace or append to a client store).

- **Decode:** every message is self-contained (CBOR, names inline).
- **Render:** a frame is also render-complete — the full model rides every frame.
- **Replace:** low-frequency state (app_state, progress) replaces its client home wholesale (idempotent).
- **Append:** log records append; they carry their own order via sequence.
- **Degrade:** a frame whose names reference data not yet present is skipped gracefully, never silently wrong.

## The envelope (full names, never abbreviated)

| field | type | meaning |
|---|---|---|
| kind | string | which client handler consumes it |
| version | int | message-shape version (0 for now) |
| timestamp | float | monotonic seconds (the frame clock) |
| sequence | int | monotonic within a kind, per connection (drop/order detection) |
| … | | kind-specific payload fields |

An unknown kind or an unsupported version is skipped + logged (fail soft — inbound data), never crashes
and never decodes wrongly.

## Kinds (flat, split by source)

| kind | payload | sent | client home |
|---|---|---|---|
| frame | frame_number, model_sequence, convention, cameras, models, instances, trackers, image | every frame | frame subscribers (fast) |
| log | record | on emit | LogStore (append) |
| framerate | camera_group_id, backend_framerate, frontend_framerate | on emit | FramerateStore (fast) |
| app_state | server_pid, state | connect + on change | connection slice (replace) |
| progress | pipeline progress | on emit | pipelines/mocap/calibration slices (replace) |

On connect the relay sends the current value of the replace kinds (app_state), then streams frames. A
later change sends a fresh full replacement. Calibration is NOT a websocket kind: the frontend loads it
over HTTP (`loadCalibrationToml` / `loadCalibrationForRecording`), and the realtime reprojections are
already computed backend-side. The `convention` / `model` / `camera_layout` / `calibration`
replace-kinds of the earlier design were folded into the frame (they ride every frame as part of the
self-describing document) — see [../01-data-model/message-contract.md](../01-data-model/message-contract.md).

## The frame message

One frame of reconstruction + images, fully self-describing. The authoritative shape lives in
[../01-data-model/message-contract.md](../01-data-model/message-contract.md); the short form:

```
{
  kind: "frame", version: 0, timestamp: 123.456, sequence: 42, frame_number: 99, model_sequence: 0,
  convention: { units:"mm", handedness:"right", up_axis:"+z", forward_axis:"+x", rotation_frame:"local", rotation_form:"quaternion" },
  cameras: [ { id, index, rotation, image_size, intrinsics, extrinsics, world_position, world_orientation } ],
  models: [ { model_id, segments:[…], landmarks:[…] } ],
  instances: [ { instance_id, model_id, channels:[…] } ],
  trackers: [ { tracker_id, detector_type, model_id, channels:[…] } ],
  image: <jpeg bytes>
}
```

## Framing + codec (CBOR, pinned)

CBOR (RFC 8949) is the codec. Native byte strings carry the JPEG and the packed Float32 channel data
directly. A packed Float32Array ships as a pre-serialized little-endian byte string (major type 2) — the
channel block's `columns` already self-describes the dtype, and pre-serializing sidesteps any float16
downcast (half-precision would be silent measurement loss). float32 only, never float16; scalar floats
stay float64. Definite-length maps/arrays; the encoder emits maps in documented field order. CBOR is a
codec, not framing — the envelope's kind field is the demux.

## Ordering + flow control

Single writer, ordered — the relay serializes all sends. Newest-wins for frames (a slow client receives
fewer, newer frames; a sequence gap in frame is expected). Replace/append kinds are tiny and never
dropped. Idempotence makes gaps harmless — a missed state replacement is overwritten by the next one.

## Observability + extensibility

timestamp + per-kind sequence let a client detect drops, reordering, and cadence. A new data type is a new
kind with a declared payload shape + a client handler — no changes to the envelope, framing, relay, or
existing kinds.

## Retired (the schema/sample model)

StreamSchema, ChannelGroup, block_kind/dtype_code, the producer-composed schema, the composite signature +
schema-resend machinery, the frontend SchemaRegistry, the LSL-style schema-then-samples wire, and the
`tracker_schemas` handshake. `TrackedObjectDefinition` (the TYPE) survives — it is the playback
stick-figure's connection source, not part of this wire.
