# Stream Schema + Sample (the data contract)

**Describes (types):** `freemocap/core/streaming/standard_stream/` — `stream_schema.py`,
`stream_sample.py`, `coordinate_convention.py`, and the `producers/` package that composes both. The
**wire framing / encoder / send-path** that carries these lives in
[../03-transport/backend-encoder-ws.md](../03-transport/backend-encoder-ws.md) — this doc owns the
*shapes*, that one owns the *transport*.

## What this covers
The LSL-shaped contract: a **schema** (channel groups, joint hierarchy, T-pose, convention, units,
per-camera image sizes) sent once and **on every data-model change**, then timestamped **samples** —
**one per frame, carrying every block the current schema declares**, including the camera JPEG images.

## The one stream — schema is the single source of truth for the data model

There is **one** stream: schema-then-samples. The schema describes *whatever data currently exists*; a
sample carries one frame of exactly that. When the data model changes for any reason — a realtime
pipeline starts or stops, the detector changes, the camera set changes — the server rebuilds the schema
and resends it; the consumer replaces its copy and decodes subsequent samples against it
([lifecycle](#schema-lifecycle)). **"camera-only" vs "camera + reconstruction" is therefore not a
special case** — it is two schemas produced by one mechanism. Mode is *data* (the schema), never a code
branch.

Images are **not** a second stream. They are a channel group (`IMAGE_JPEG`) like any other — the same
category of per-camera, per-frame data as `OVERLAY_2D`. Every frame's image, overlay, and pose travel in
**one sample**, so a consumer composites overlay-N onto image-N by construction (no cross-stream timing).

## The producer model (how the schema + sample are composed)

The schema and each sample are composed from a set of **channel producers**
(`freemocap/core/streaming/standard_stream/producers/`). A producer owns a coherent slice of the data
model and declares:

- `is_active(ctx: StreamContext) -> bool` — whether it contributes right now.
- `schema_groups(ctx: StreamContext) -> list[ChannelGroup]` — the channel group(s) it declares.
- `schema_metadata(ctx: StreamContext) -> dict` — static schema fields it owns (e.g. image →
  `camera_ids` + `camera_image_sizes`; segments → `connections` / `joint_hierarchy` /
  `segment_parents` / `rest_pose` / default `segment_lengths`).
- `signature(ctx: StreamContext) -> Hashable` — a **structural** fingerprint (NOT per-frame values)
  used for change detection.
- `fill(ctx: FrameContext) -> list[SampleBlock]` — the block(s) for this frame; a missing element is a
  NaN row (occlusion) — never a dropped block. The composer binds the composition's `StreamContext`
  onto the `FrameContext` so stateless producers can resolve the schema's declared names.

`FrameContext` carries `frame_number`, `timestamp`, `aggregator_output` (the shared
`AggregationNodeOutputMessage`, or `None` in camera-only mode), and `image_payload` (the SkellyCam
multi-camera JPEG bytes for that frame).

The schema is the union of the active producers' groups + metadata, in a fixed producer order; a sample
is the concatenation of the active producers' filled blocks. New data types (a face-blendshape stream, an
audio stream, per-camera reprojections) are **new producers** — no changes to the codec, the relay, or
the consumer's demux. The initial producers, in composition order (channel-table order — `IMAGE_JPEG`
composes **last** so its odd-length uint8 blob never precedes a float32 block):

| Producer | Active when | Groups it contributes |
|---|---|---|
| `KeypointsProducer` | a realtime pipeline is live | `KEYPOINTS_3D`, `LANDMARKS_3D` |
| `SegmentProducer` | a realtime pipeline is live | `SEGMENT_ORIGINS`, `ROTATIONS_LOCAL`, `ROTATIONS_WORLD`, `SEGMENT_LENGTHS` (+ hierarchy / parents / connections / rest_pose / `segment_axes` — each segment's long-axis basis name, the EXACT axis declaration: body/hand = `y`, face = `z`; the 3D bone renderer orients its unit geometry onto it) |
| `OverlayProducer` | a realtime pipeline is live | `OVERLAY_2D` + `OVERLAY_REPROJECTIONS` (per camera each) |
| `DerivedProducer` | a realtime pipeline is live | `DERIVED_POINTS` |
| `ImageProducer` | cameras exist (always, in every mode) | `IMAGE_JPEG` (+ `camera_ids` / `camera_image_sizes`) |

The reconstruction producers all read the **same** aggregator output from the shared `FrameContext`, so
there is exactly one consumer of the aggregator output — no draining race.

## The channel table

Fixed producer-determined order; each block is **self-describing** (its header carries `block_kind`,
`dtype_code`, `camera_id`, `overlay_layer`), so consumers resolve **by kind**, not by position.

| Kind | Group | Names | Columns | dtype |
|---|-------|-------|---------|-------|
| 0 | `KEYPOINTS_3D` | tracker-named measured keypoints | `x, y, z, reprojection_error` | float32 |
| 1 | `LANDMARKS_3D` | the 76 hydrated landmarks | `x, y, z, reprojection_error` | float32 |
| 2 | `SEGMENT_ORIGINS` | the 60 segment names | `x, y, z` | float32 |
| 3 | `ROTATIONS_LOCAL` | the 60 segment names | `w, x, y, z` | float32 |
| 4 | `ROTATIONS_WORLD` | the 60 segment names | `w, x, y, z` | float32 |
| 5 | `DERIVED_POINTS` | `center_of_mass`, `xcom` | `x, y, z` | float32 |
| 6 | `OVERLAY_2D` | per camera (DETECTIONS layer) | `x, y, visibility` | float32 |
| 7 | `SEGMENT_LENGTHS` | the 60 segment names | `length_mm` | float32 |
| 8 | `IMAGE_JPEG` | per stream (one opaque block) | JPEG bytes | uint8 |
| 9 | `OVERLAY_REPROJECTIONS` | per camera — the fitted skeleton's segment-origin landmarks projected back into the camera | `x, y, visibility` | float32 |

- **`SEGMENT_LENGTHS` is sent every frame.** Segment lengths are per-frame data (the estimators converge
  over the stream), so they live in the sample, not the schema. This retires the old "resend the schema
  when lengths change materially" machinery — length changes never touch the schema. The schema's
  `rest_pose` still carries anthropometric **default** lengths so a consumer can render before the first
  sample arrives; per-frame `SEGMENT_LENGTHS` overrides once samples flow.

- **`IMAGE_JPEG` carries the camera images.** One opaque block per sample = the SkellyCam multi-camera
  frontend-payload bytes for that frame (`dtype_code = UINT8`). The block is opaque to the standard
  stream; the consumer's existing frame decoder splits it per camera. *(A per-camera `IMAGE_JPEG` block
  set — symmetric with `OVERLAY_2D` — is the clean future shape; the opaque form is used first because it
  reuses the existing decoder and needs no SkellyCam change.)*

- **The 2D overlays (kinds 6 + 9) are capture-resolution image px**; the schema's **`camera_image_sizes`**
  (`{camera_id: [width, height]}`, owned by `ImageProducer`) declares each camera's capture size, and
  consumers scale overlay points to their own display size with it. `visibility` carries the tracker's
  confidence (0–1).
  - **`OVERLAY_2D` (DETECTIONS)** — the tracker's raw 2D keypoints (59 tracker names) — drawn as small
    dots.
  - **`OVERLAY_REPROJECTIONS`** — the fitted skeleton's **segment-origin landmarks** (60 segment names)
    projected back into each camera — drawn as larger dots with the schema's `connections` (segment
    parent→child edges) between them. Requires a valid calibration; NaN rows (2D-only mode) are simply
    nothing drawn.

- **Dual point channels:** `KEYPOINTS_3D` carries the **tracker-named measured keypoints** (the raw,
  un-mapped triangulations; names from
  `freemocap/core/tasks/mocap/tracker_mappings.py::tracker_keypoint_names(detector_type)`).
  `LANDMARKS_3D` carries the **76 hydrated standard-human landmarks** (model-side named points after
  mapping; a missing frame = a NaN row).

## dtype codes

`DtypeCode`: `FLOAT32 = 0` (all point / rotation / scalar blocks) and `UINT8 = 1` (raw bytes — the
`IMAGE_JPEG` block). The block header's `data_byte_length` is authoritative for how many bytes a block's
data occupies; only float32 blocks satisfy `data_byte_length == num_elements × cols × 4`.

## Schema lifecycle

- Built by composing the **active producers** at connect and whenever the data model changes.
- **Change detection is a signature:** the supervisor holds a composite signature = the ordered tuple of
  active producers' `signature()`. When it differs from the last-sent schema's, the schema is rebuilt and
  resent. This single mechanism replaces the old per-cause checks (camera-set change, detector change,
  and the retired length-change check).
- **Ordering guarantee:** the schema is always sent before any sample formatted to it — the single-writer
  `SendSerializer` (see [../03-transport/backend-encoder-ws.md](../03-transport/backend-encoder-ws.md))
  serializes the rebuild→send-schema→send-samples sequence, so a consumer never sees a sample it cannot
  decode.

## The producer↔consumer contract (load-bearing)

The producer may emit **any valid schema variation** — image-only (camera-only mode, before a pipeline is
live), image + full reconstruction, or any future producer set. Correspondingly, **every consumer MUST
gracefully handle whatever schema it receives**, including a schema that omits a channel group the
consumer cares about. A consumer that assumes a group is always present — and breaks when it is absent —
is **the defect**; a producer emitting a valid partial schema is **not**. This is a system-wide invariant,
not a per-consumer special case: resolve-a-group logic should degrade to "draw/emit nothing for that
group," never throw. *(A concrete violation: the 3D bone renderer once threw on the image-only schema
because it assumed `SEGMENT_ORIGINS` was always present — that is the class of bug this contract forbids.)*

## Reconciliation notes
`wxyz` quaternions; convention block = the [00-foundation/conventions.md](../00-foundation/conventions.md)
facts, single-sourced (the schema *states* them, doesn't redefine them). Names live in the schema, not in
the sample.
