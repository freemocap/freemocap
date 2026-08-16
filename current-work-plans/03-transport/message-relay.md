# Backend Message Relay + WebSocket Send-Path

> **Status: IMPLEMENTED** — the backend now matches this doc (see HANDOFF.md for the verified green state).

**Describes:** freemocap/api/websocket/ — send_serializer.py, frame_relay.py, websocket_server.py —
recomposed as a single **message relay** that emits typed, self-describing messages instead of a schema
plus binary samples. This completes the websocket_server.py breakup in the archived spec 06.

## Architecture

One relay, one consumer of the aggregator output. Each tick it composes the frame message from the
channel sources; the replace-kinds (convention, model, camera_layout, calibration, app_state) are emitted
on connect and re-emitted whole when their source changes. There is no schema build and no signature/
resend machinery.

### The frame message

The relay builds the frame channels from the same sources used today: keypoints, segments,
overlays, derived points, and the camera image bytes. Each channel is a named column block (kind + names +
columns + data). The image rides the frame as the image field (the opaque multi-camera JPEG blob).

### The replace-kinds

Each replace-kind is owned by the source that knows it:

- convention + model + camera_layout — built from the standard human + camera group (today: the schema).
- calibration — from the calibration state (today: the TOML the aggregator hot-reloads).
- app_state — from FreemocapApplication.to_state_dict (unchanged).

On connect the relay sends each one once; on any change it sends a fresh full replacement. No gathering,
no composite signature — each source emits its own update.

### The log / framerate / progress kinds

These are append/telemetry kinds, not state: log (from the log queue), framerate (from the framerate
reporter), progress (from posthoc pipeline progress). The relay emits them as they occur, each with its
own sequence. This replaces the several ad-hoc send loops (log relay, app-state sender, framerate
calculation, posthoc progress) with one kind-dispatched emit path.

## Send serializer (unchanged)

One asyncio.Lock serializes every write. Because all messages are self-describing, ordering is the only
invariant the serializer must preserve — there is no schema-before-samples ordering to maintain.

## Flow control (unchanged)

Newest-wins for frames (a slow client gets fewer, newer frames). Replace-kinds are tiny and never dropped.
The inbound frameAcknowledgment stays, carrying only displayImageSizes (SkellyCam downscaling).

## Codec

CBOR via cbor2, one message per socket write. The envelope kind field is the demux on the client.

## WebsocketServer becomes a thin supervisor

Mirroring the frontend, websocket_server.py shrinks to a thin supervisor that wires: the frame relay, the
replace-kind emitters, the log/framerate/progress emitters, the send serializer, and the inbound client-
message handler. Each is a focused, testable component.