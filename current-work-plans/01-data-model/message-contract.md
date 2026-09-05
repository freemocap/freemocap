# The Message Contract (the message types)

**Describes:** the five message kinds and their payload shapes — the single self-describing wire contract.
The backend encodes to it (`freemocap/core/streaming/message_model.py`, cbor2) and the frontend validates
against it (`freemocap-ui/.../transport/message-contract.ts`, cbor-x + Zod). Framing / send-path lives in
[../03-transport/message-protocol.md](../03-transport/message-protocol.md); the backend relay in
[../03-transport/message-relay.md](../03-transport/message-relay.md); the client dispatcher in
[../04-ui/ui-integration.md](../04-ui/ui-integration.md).

## Envelope (every message)

Every message carries `kind` (which handler), `version` (shape version, 0), `timestamp` (monotonic
seconds), `sequence` (monotonic within a kind, per connection), then the kind payload. Full names, never
abbreviated. The payload fields spread into each kind variant.

## Kinds (the five kinds)

| kind | payload | client home |
|---|---|---|
| frame | frame_number, model_sequence, convention, cameras, models, instances, trackers, image | frame subscribers (fast) |
| log | record (a logging record) | LogStore (append) |
| framerate | camera_group_id, backend_framerate, frontend_framerate | FramerateStore (fast) |
| app_state | server_pid, state (camera groups + realtime pipelines) | connection slice (replace) |
| progress | pipeline_id, pipeline_type, phase, progress_fraction, detail, recording_name, recording_path, camera_id | pipelines/mocap/calibration slices (replace) |

Adding a kind = one variant + one handler entry. An unknown kind or unsupported version is skipped +
logged (fail soft — inbound data).

## The frame message (fully self-describing)

A frame is a complete document — one frame decodes AND renders with zero prior state (there is no
decode-vs-render split and no held descriptor). It carries:

- `convention` — `CoordinateConvention` (units, handedness, up_axis, forward_axis, rotation_frame,
  rotation_form).
- `cameras` — one `CalibratedCamera` per camera: id, index, rotation, image_size, intrinsics,
  extrinsics, world_position, world_orientation. `rotation` + `image_size` define the ROTATED
  overlay/JPEG coordinate space.
- `models` — `ModelDefinition`: model_id, ordered `segments` (name, parent, primary_axis,
  rest_orientation wxyz, **`length_proportion`**, is_fully_specified), ordered `landmarks` (name,
  rest_position), and the structure a client needs in order to draw it without inventing anything:
  - `connections` — `(parent_segment, child_segment)` name pairs derived once from the joint topology.
  - `landmark_connections` — named **connection groups** (`charuco_grid`, `aruco_markers`,
    `skull_outline`), each a list of landmark pairs plus its resolved colour.
  - `landmark_groups` — named sets of landmarks plus a resolved colour, so a client colours a point
    by what it *is* rather than by what its name starts with.

  Colours are RESOLVED before they go on the wire: the model carries tags, a palette turns them into
  colours, and the frame carries the answer — so a client never needs the palette, and swapping the
  palette recolours every client at once.
  - `scale_reference_name` — what this model's `1.0` means (`body_height`, `square_length`).

  The model is the single source of truth for structure: clients draw these edges and groups directly
  and never re-derive them from names, config, or hierarchy fields. The model is **dimensionless** —
  lengths and rest positions are fractions of `scale_reference_name` — so a size lives on the instance.
- `instances` — `ModelInstance`: instance_id, model_id, channels, and `fitted_scale_mm` — this
  occurrence's fitted size in the unit the model names, absent until something has measured it (which
  means "no size", not "assume a default"). Multiply a segment's `length_proportion` by it for
  millimetres, or prefer the `SEGMENT_LENGTHS` channel, which carries fitted millimetres for every
  segment whether or not it was visible
  ([../02-pipeline/model-scale-fitting.md](../02-pipeline/model-scale-fitting.md)).
- `trackers` — `TrackerObservation`: tracker_id, detector_type, model_id, channels.
- `image` — the camera image bytes.

**`models`, `instances` and `trackers` are plural, always.** A tracked human and a tracked charuco
board are two models; two people are two instances of one model; a pose detector and a charuco
detector are two tracker observations. No consumer on either side of the wire may assume one of any
of them ([../07-generic-skeletons/design.md](../07-generic-skeletons/design.md)).

## The channel block

A frame channel is a `ChannelBlock`: `kind` + `columns` + `data` (packed float32 little-endian
bytes, columns by names, row-major), plus `camera_id` (per-camera overlay channels only) and `names`
(inline, on tracker-keypoint channels). Segment/landmark channels are **index-keyed** — row order is the
model's ordered segments/landmarks, so those names are dropped. Channel kinds: KEYPOINTS_3D,
LANDMARKS_3D, SEGMENT_ORIGINS, ROTATIONS_LOCAL, ROTATIONS_WORLD, DERIVED_POINTS, OVERLAY_2D,
SEGMENT_LENGTHS, OVERLAY_REPROJECTIONS, JOINT_ANGLES.
