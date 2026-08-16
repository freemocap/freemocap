# The Message Protocol (self-describing; no schema, no samples)

> **Status: IN PROGRESS — step 1 landed (contract + codec + parity test, additive).** The committed wire
> still runs schema-then-samples; steps 2–5 below replace it. See the preservation inventory in
> 04-ui/ui-integration.md.

**Describes:** the wire behavior — one WebSocket carrying a stream of **self-describing messages**.
There is no schema and no samples. Every message is typed, versioned, and carries everything needed to
decode it, so a client holds no reconstruction state and can never decode against a stale descriptor.

This doc folds into (and supersedes) the earlier ServerContextProvider/WebsocketServer decomposition plans
(archive specs 05 and 06, archive plan 04-ui-wedge): the message model below is the single mechanism that
replaces, at once, the frontend message_type if/else chain, the binary schema/sample demux, the
hand-rolled isX type guards, and the backend's several ad-hoc send loops.

## Why

The old schema-then-samples wire made the client's ability to decode depend on a separately-held
descriptor. That is a **stateful coupling**: the descriptor and the data can fall out of sync — and worse,
*silently*, because nothing in a sample says which descriptor it assumes. Two processes that start, stop,
and reconnect independently (browser + server) make that desync a permanent liability, not an edge case.

Self-describing messages remove the coupling: any message can be interpreted on its own terms. The second-
order win is surface-area reduction — a held descriptor needs change-detection, a resend lifecycle, and an
ordering guarantee that the descriptor precedes its data; a self-describing stream collapses all of that to
the single invariant a one-writer lock already gives us (send order).

Two properties are easy to conflate: **decode-complete** (can I turn bytes into typed values with zero prior
state?) vs **render-complete** (can I *use* those values with zero prior state?). We buy the first with
CBOR + inline names; the second we deliberately do not chase (see below), and being honest about that
boundary is what keeps the design from lying to us later.

CBOR (not JSON / MessagePack / Protobuf) because it is the standards-track self-describing *binary* format:
native byte strings carry the dominant JPEG payload and the packed Float32 arrays directly (no base64,
no typed-array tag ambiguity), and its deterministic profile gives reproducible bytes for exact cross-language parity.
The bandwidth reality settles it: with four cameras of JPEG per frame the entire non-image payload is ~5%,
so the metadata channel is optimized for robustness and clarity, not bytes.

## The model

The stream is a sequence of **messages**. Each message declares a **kind** (which handler consumes it) and
a **shape version**, then its payload. Kinds differ only in cadence (some every frame, some on change)
and consumption (frames emit to renderers; the rest replace a client store/slice). There is no static-vs-
dynamic category: a value that changes rarely is just an update sent rarely.

- **Decode:** every message is self-contained (CBOR, names inline). No prior state required.
- **Replace:** a low-frequency message replaces its client home wholesale (idempotent: N applies == one).
- **Append:** stream-like messages (logs) append; they carry their own order via sequence.
- **Degrade:** a frame whose names reference data not yet present is skipped gracefully, never silently wrong.

## Decode-complete vs render-complete (the honesty boundary)

A frame is **decode-complete**: its bytes turn into typed values (names, numbers, quaternions) with zero
prior state. It is NOT **render-complete**: drawing bones still needs the model slice (rest orientations,
axes, connections), which the client holds as state and joins by name. We deliberately do not chase
render-completeness — that honesty is what keeps the design from overclaiming "never stale." Within one
connection, correctness is guaranteed by ordering: the single writer sends a changed model before the
frames that assume it.

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
| frame | frame_number, subjects, image | every frame | frame subscribers (fast) |
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
to any kind sends a fresh full replacement. Calibration is one of these replace-kinds: the aggregator's
existing hot-reload is its source, and a calibration change is emitted as a fresh calibration message — no
side path.

## The frame message

One frame of reconstruction + images, fully self-describing. The authoritative channel/shape types
live once in ../01-data-model/message-contract.md; below is the wire illustration:

```
{
  kind: "frame", version: 0, timestamp: 123.456, sequence: 42, frame_number: 99,
  subjects: [
    {
      subject_id: 0,
      channels: [
        { kind: "SEGMENT_ORIGINS", names: ["hips","spine",...], columns: ["x","y","z"], data: <60x3 f32 bytes> },
        { kind: "ROTATIONS_WORLD", names: [...], columns: ["w","x","y","z"], data: <60x4 f32 bytes> },
        ...
      ],
    }
  ],
  image: <jpeg bytes>
}
```

Each channel is a named column block: kind + names + columns + data (a byte string of packed float32 or
uint8). Names are inline, so the client decodes the block with zero state. The layout (columns x names,
row-major) is fixed by columns; there is no dtype registry.

The reconstruction channels: KEYPOINTS_3D, LANDMARKS_3D, SEGMENT_ORIGINS, ROTATIONS_LOCAL,
ROTATIONS_WORLD, SEGMENT_LENGTHS, DERIVED_POINTS, OVERLAY_2D, OVERLAY_REPROJECTIONS. Segment lengths ride
the frame (per-frame data), not a replace-kind. Images ride the frame as img (the opaque multi-camera blob
for now; per-camera channels later).

## Framing + codec (CBOR, pinned)

CBOR (RFC 8949) is the codec. Why it wins here:

- Native byte strings — the JPEG payload and the packed float32 channel data both ride directly as
  fields (no base64 tax; this rules out plain JSON as the top-level container).
- Plain byte strings, not typed-array tags — a packed Float32Array ships as a pre-serialized
  little-endian byte string (major type 2). The channel block's `columns` already self-describes the
  dtype, so RFC 8746 typed-array tags add a cbor2-vs-cbor-x tag-encoding identity risk for no decode
  benefit. Pre-serializing to bytes also sidesteps the float16 downcast entirely: the float32 packing is
  the producer's job, not the encoder's.
- A real IETF standard with a deterministic profile — reproducible bytes (cbor2 in Python, cbor-x in JS).

The encoding is pinned, not left to encoder defaults:

- float32 only, never float16 — packed arrays are pre-serialized to float32 bytes before CBOR, so no
  encoder downcast can touch them (half-precision would be silent measurement loss). Scalar floats
  (timestamp, progress_fraction) stay float64.
- definite-length maps/arrays; the encoder emits maps in the documented field order (kind, version,
  timestamp, sequence, then the payload). The decoder does not care about key order.

CBOR is a codec, not framing: the envelope's kind field is the demux. A CBOR self-describe tag (55799) is
available but unnecessary.

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

## Pre-swap audit (2026-08-15) — locked corrections & decisions

Verified against the committed code before the cutover. These supersede any looser wording elsewhere in these docs.

- **Calibration stays HTTP (kind reserved, not emitted).** The frontend loads calibration over HTTP
  (`loadCalibrationToml` via Electron tRPC; `loadCalibrationForRecording` via `fetch`), not the
  websocket; the realtime reprojections are already computed backend-side. The `calibration` kind is
  reserved for a future live push — no parallel path is built speculatively.
- **`tracker_schemas` handshake is dead, but `TrackedObjectDefinition` is not.** The realtime handshake
  is removed (backend source already deleted). The `TrackedObjectDefinition` TYPE, `ConnectionRenderer`,
  `getActiveSchema`, `buildSegmentsFromSchema`, and `virtual-points` remain — they are the **playback**
  stick-figure's connection source (`FileKeypointsSourceProvider` forwards `bundle.trackerSchema`). The
  swap deletes the handshake only.
- **`charuco` is half-dead.** The 2D charuco *overlay* is dead (the offscreen worker always receives a
  null charuco observation). Charuco *calibration* (board config + pipeline) is live. The 3D
  `ConnectionRenderer` charuco/aruco grid draws `CharucoCorner-*`/`ArucoMarkerCorner-*` keypoints that
  are no longer on the realtime wire — confirm the playback path before deleting that code.
- **Framerate is inline, not a task.** Today framerate is sent from the frame source (250 ms throttle),
  not a separate loop. The `framerate` kind emitter replaces that inline path.
- **`app_state` has cross-slice listeners.** `serverStateReceived` (connection slice) is also consumed by
  the cameras + realtime slices; the `app_state` kind dispatches the same action and that reconciliation
  must survive.
- **`stream_id` / `stream_name` / `max_persons` are dropped.** Nothing in the frontend consumes them
  (they exist only in the schema type + test fixtures). The connection is the stream (identity =
  `server_pid` in `app_state`); multi-subject rides the frame's self-describing `subjects` array — no
  fixed `max_persons`.
- **The 3D renderer re-points to `model`.** `RigidBodyBoneRenderer` + `KeypointsSource` read
  `subscribeToSchema`/`getStreamSchema` today. After the swap they read the `model` kind (rest
  orientations + axes + lengths + connections); `KeypointsSource` gains `subscribeToModel`/`getModel`.
- **Playback keeps its own schema path.** `model` is the realtime source; playback continues to load
  `trackerSchema` over HTTP. Not merged in this swap.
- **Contract refinements (locked while authoring `message-contract.ts`):** the frame channel block gains
  an optional `camera_id` (per-camera overlays; the old `overlay_layer` byte folds into the two distinct
  channel kinds). `model` carries ordered `segments` + `lengths` (the bone renderer's name→index +
  schema-time length source) in addition to `orientations`/`axes`/`connections`/`hierarchy`/
  `rest_positions`. `convention` keeps `rotation_frame` (the old `CoordinateConvention` had it).
  `progress` keeps `recording_name`/`recording_path`/`camera_id` (the current `PipelineProgressMessage`
  shape).

## Build order (the cutover)

Hard cutover, no dual format. Nothing downstream is loadbearing yet, so the app may be broken between steps
2 and 3 — that window is accepted and brief.

**Checkpoint first (user, owns git): commit the working tree** — a known-good rollback point, since the
full loop is only verifiable manually with cameras.

1. **Contract + codec (additive).** New message-contract.ts: the Zod discriminated union (envelope + all
   kinds) and the channel block. Add CBOR decode (cbor-x) / encode (cbor2) behind a thin codec. Golden-byte
   parity test: Python encodes a message, TS decodes it and asserts equality. No behavior change.

2. **Backend emit.** Replace the producer-composed schema+samples and the ad-hoc JSON send loops with one
   message emitter: frame (self-describing channels) plus the replace-kinds (convention, model,
   camera_layout, calibration) plus log / framerate / app_state / progress. websocket_server.py becomes a
   thin supervisor over focused emitters. (App breaks here until step 3.)

3. **Frontend dispatch.** Generalize RoutingTable into a kind dispatcher; TransportService decodes CBOR,
   validates against the union, and routes each kind to its home (RTK slice replace vs fast store
   append/emit). Restores the app.

4. **Delete old + shrink.** Remove StreamSchema / ChannelGroup / SchemaRegistry, the isX guards, and the
   schema/sample decode path. Move the frame decode/ack loop out of ServerContextProvider into a rendering
   module; shrink the provider to a thin composition root.

5. **Verify preservation.** Walk the inventory in ../04-ui/ui-integration.md and confirm each live behavior
   (F5 gate plus the existing harnesses).