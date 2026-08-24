# Backend Message Relay + WebSocket Send-Path

**Describes:** `freemocap/api/websocket/` — the backend that composes and emits the self-describing
message stream (frame + log + framerate + app_state + progress) over one WebSocket. `websocket_server.py`
is a thin supervisor over focused emitters.

## Architecture

One relay, one consumer of the aggregator output (`AggregationNodeOutputMessage`). `websocket_server.py`
holds its own `SkeletonDefinition` + `RestPose` in a `StreamContext` — recomposed when its signature
(cameras, detector type, live state) changes — and hands each frame to `message_composer.compose_messages`:

- **Static rows** (once per composition): `CoordinateConvention`, one `CalibratedCamera` per camera,
  `ModelDefinition.from_standard_human(skeleton=..., rest_pose=...)` (segments, landmarks, connections).
- **Per-frame producers**, each filling its channel blocks: `KeypointsProducer` (KEYPOINTS_3D
  tracker-named + LANDMARKS_3D standard-human-named), `SegmentProducer` (SEGMENT_ORIGINS,
  ROTATIONS_LOCAL/WORLD, SEGMENT_LENGTHS), `DerivedProducer` (DERIVED_POINTS:
  `center_of_mass`, `xcom`), `OverlayProducer` (OVERLAY_2D + OVERLAY_REPROJECTIONS per camera).

The state/telemetry kinds (log, framerate, app_state, progress) are emitted as they occur, each with its
own sequence. There is no schema build and no signature/resend machinery — every message is
self-describing.

## The frame message

The relay builds the frame channels from the same sources used today. Each channel is a `ChannelBlock`
(kind + columns + data, index-keyed against the model's ordered segments/landmarks; tracker-keypoint
channels carry inline names). The image rides the frame as the `image` field. The frame also carries
`convention`, `cameras` (calibrated, from the live camera config + calibration), `models` (the
standard human), `instances`, and `trackers` — see
[../01-data-model/message-contract.md](../01-data-model/message-contract.md).

## The state / telemetry kinds

- `app_state` — from `FreemocapApplication.to_state_dict` (camera groups + realtime pipelines), sent on
  connect and re-sent when it changes.
- `log` — from the log queue (append).
- `framerate` — from the framerate reporter (backend + frontend telemetry).
- `progress` — from posthoc pipeline progress.

This replaces the several ad-hoc send loops (log relay, app-state sender, framerate calculation, posthoc
progress) with one kind-dispatched emit path.

## Send serializer

One `asyncio.Lock` serializes every write. Because all messages are self-describing, ordering is the only
invariant the serializer must preserve — there is no schema-before-samples ordering to maintain.

## Flow control

Newest-wins for frames (a slow client gets fewer, newer frames). State/telemetry kinds are tiny and never
dropped. The inbound frameAcknowledgment stays, carrying only displayImageSizes (SkellyCam downscaling).

## Codec

CBOR via cbor2, one message per socket write. The envelope kind field is the demux on the client.

## WebsocketServer is a thin supervisor

`websocket_server.py` wires: the frame relay, the state/telemetry emitters, the send serializer, and the
inbound client-message handler. Each is a focused, testable component.
