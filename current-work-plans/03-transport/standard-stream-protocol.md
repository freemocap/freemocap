# The Message Protocol (self-describing; no schema, no samples)

> **Status: PLANNED — design locked, not yet implemented.** The committed code still implements the
> schema-then-samples model; this doc is the target for the swap. See the preservation inventory in
> 04-ui/ui-integration.md and the decision in IMPLEMENTATION_PLAN.md.

**Describes:** the wire behavior — one WebSocket carrying a stream of **self-describing messages**.
There is no schema and no samples. Every message is typed, versioned, and carries everything needed to
decode it, so a client holds no reconstruction state and can never decode against a stale descriptor.

This doc folds into (and supersedes) the earlier ServerContextProvider/WebsocketServer decomposition plans
(archive specs 05 and 06, archive plan 04-ui-wedge): the message model below is the single mechanism that
replaces, at once, the frontend message_type if/else chain, the binary schema/sample demux, the
hand-rolled isX type guards, and the backend's several ad-hoc send loops.

## The model

The stream is a sequence of **messages**. Each message declares a **kind** (which handler consumes it) and
a **shape version**, then its payload. Kinds differ only in cadence (some every frame, some on change)
and consumption (frames emit to renderers; the rest replace a client store/slice). There is no static-vs-
dynamic category: a value that changes rarely is just an update sent rarely.

- **Decode:** every message is self-contained (CBOR, names inline). No prior state required.
- **Replace:** a low-frequency message replaces its client home wholesale (idempotent: N applies == one).
- **Append:** stream-like messages (logs) append; they carry their own order via sequence.
- **Degrade:** a frame whose names reference data not yet present is skipped gracefully, never silently wrong.

## The envelope (full names, never abbreviated)

Every message is a CBOR map with this envelope:

| field | type | meaning |
|---|---|---|
| kind | string | which client handler consumes it |
| version | int | message-shape version (0 for now) — the envelope/payload contract for this kind |
| timestamp | float | monotonic seconds (the frame clock) |
| sequence | int | monotonic within a kind, per connection (drop/order detection) |
| ... | | kind-specific payload fields |

An unknown kind or an unsupported version is skipped + logged (fail soft — inbound data), never crashes
and never decodes wrongly.

## Kinds (flat, split by source — no umbrella kinds)

| kind | payload | sent | client home |
|---|---|---|---|
| frame | n, ch, img | every frame | frame subscribers (fast) |
| convention | units, handedness, up_axis, forward_axis, rotation_form | connect + on change | RTK slice (replace) |
| model | orientations, axes, hierarchy, connections, rest_positions | connect + on change | RTK slice (replace) |
| camera_layout | camera_ids, image_sizes | connect + on change | RTK slice (replace) |
| calibration | camera intrinsics/extrinsics | connect + on change | RTK slice (replace) |
| log | log records | on emit | LogStore (append) |
| framerate | backend/frontend framerate telemetry | on emit | FramerateStore (fast) |
| app_state | server state snapshot | connect + on change | RTK slice (replace) |
| progress | posthoc pipeline progress | on emit | RTK slices (replace) |

Split by **source of truth**, not by consumer convenience. Nothing is lumped under a status/config/
state umbrella. New kinds (timing reports, streaming status, ...) are added flat alongside these.

On connect the relay sends the current value of every replace-kind, then streams frames. A later change
to any kind sends a fresh full replacement. Calibration may be sourced from the existing TOML hot-reload
or pushed directly — it is one kind either way (see the migration note).

## The frame message

One frame of reconstruction + images, fully self-describing:

```
{
  kind: "frame", version: 0, timestamp: 123.456, sequence: 42, n: 99,
  ch: [
    { kind: "SEGMENT_ORIGINS", names: ["hips","spine",...], cols: ["x","y","z"], data: <60x3 f32 bytes> },
    { kind: "ROTATIONS_WORLD", names: [...], cols: ["w","x","y","z"], data: <60x4 f32 bytes> },
    ...
  ],
  img: <jpeg bytes>
}
```

Each channel is a named column block: kind + names + cols + data (a byte string of packed float32 or
uint8). Names are inline, so the client decodes the block with zero state. The layout (cols x names,
row-major) is fixed by cols; there is no dtype registry.

The reconstruction channels: KEYPOINTS_3D, LANDMARKS_3D, SEGMENT_ORIGINS, ROTATIONS_LOCAL,
ROTATIONS_WORLD, SEGMENT_LENGTHS, DERIVED_POINTS, OVERLAY_2D, OVERLAY_REPROJECTIONS. Segment lengths ride
the frame (per-frame data), not a replace-kind. Images ride the frame as img (the opaque multi-camera blob
for now; per-camera channels later).

## Framing + codec

CBOR (RFC 8949) is the codec — self-describing like JSON, but compact and with deterministic encoding
(cbor2 in Python, cbor-x in JS; both handle float32/uint8 natively). CBOR is a codec, not framing: the
envelope's kind field is the demux. A CBOR self-describe tag (55799) is available but unnecessary.

## Ordering + flow control

- Single writer, ordered — the relay serializes all sends; a consumer sees messages in send order.
- Newest-wins for frames — a slow client receives fewer, newer frames (a sequence gap in frame is
  expected, not an error). Replace-kinds are tiny and never dropped.
- Idempotence makes gaps harmless — a missed model/convention replacement is overwritten by the next one;
  no replay needed.

## Observability

- timestamp + per-kind sequence let the client (and any observer) detect drops, reordering, and cadence.
- Kinds and channel kinds are strings; payloads are self-describing CBOR — a message can be dumped and
  read without a spec.
- Unknown kind / bad version logs once and skips.

## Extensibility

A new data type is a new kind with a declared payload shape and a client handler — no changes to the
envelope, framing, relay, or existing kinds.

## Retired (this doc replaces the schema/sample model)

StreamSchema, ChannelGroup, block_kind/dtype_code, the producer-composed schema, the composite signature +
schema-resend machinery, and the frontend SchemaRegistry name-resolution layer. The message model above is
the whole contract.