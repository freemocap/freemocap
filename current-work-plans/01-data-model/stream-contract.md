# The Message Contract (the message types)

**Describes (types):** the message envelope, the kind list, the self-describing channel block, and each
kind payload shape. The frontend holds these as a single Zod discriminated union keyed on kind. The wire
framing/send-path lives in ../03-transport/standard-stream-protocol.md; the backend relay in
../03-transport/backend-encoder-ws.md; the client dispatcher in ../04-ui/ui-integration.md.

## Envelope (every message)

Every message carries: kind (which handler), version (shape version, 0 for now), timestamp (monotonic
seconds), sequence (monotonic within a kind, per connection), then the kind payload. Full names, never
abbreviated. The payload fields spread into each kind variant.

## Kinds (the discriminated union)

| kind | payload fields | client home |
|---|---|---|
| frame | n, ch (channel array), img (jpeg bytes) | frame subscribers (fast) |
| convention | units, handedness, up_axis, forward_axis, rotation_form | RTK slice (replace) |
| model | orientations, axes, hierarchy, connections, rest_positions | RTK slice (replace) |
| camera_layout | camera_ids, image_sizes | RTK slice (replace) |
| calibration | camera intrinsics/extrinsics | RTK slice (replace) |
| log | log records | LogStore (append) |
| framerate | backend/frontend framerate telemetry, camera_group_id | FramerateStore (fast) |
| app_state | server_pid, state | RTK slice (replace) |
| progress | pipeline_id, pipeline_type, phase, progress_fraction, detail | RTK slices (replace) |

Adding a kind = adding one variant + one handler entry. An unknown kind or unsupported version fails the
union and is logged once + skipped.

## The channel block (inside frame)

A frame channel is: kind (a string such as SEGMENT_ORIGINS or ROTATIONS_WORLD), names (the inline string
list), cols (the column names), and data (packed float32 or uint8 bytes, cols by names, row-major).
Self-describing: names inline, layout fixed by cols. The old ChannelGroup / block_kind / dtype_code are
retired.

## Client homes (the two consumption shapes)

| home | pattern | kinds |
|---|---|---|
| RTK slice | replace (idempotent, last-wins) | convention, model, camera_layout, calibration, app_state, progress |
| fast store | append, or latest + ring buffer (no re-render) | log, framerate, frame |

The dispatcher in TransportService routes each kind to its home. The homes themselves are unchanged from
today: LogStore, FramerateStore, the frame subscribers, and the existing RTK slices.

## Retired types

StreamSchema, ChannelGroup, RestPose-as-schema, DecodedSample/TypedArrayBlock (the schema-resolved sample),
SchemaRegistry, and the hand-rolled isX type guards. Replaced by the union above.