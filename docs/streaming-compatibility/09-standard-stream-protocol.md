# 09 — Standard Stream Protocol (the contract)

> The precise wire contract for the standard stream. [01](01-canonical-data-model.md) gives the
> *concepts* (schema vs. sample, what the frame carries); this doc pins the *fields and layout* that
> the backend encoder, the UI decoder, and the LSL route all implement against. It is written as an
> **evolution of the code that already exists**, not a greenfield format.
>
> Terminology — *keypoint* / *landmark* / *segment* — is defined in
> [13](13-tracker-to-canonical-mapping.md#two-kinds-of-trajectory).
>
> Status: **partly implemented** — the contract types + codecs exist
> (`freemocap/core/streaming/standard_stream/`, tests green); the six-group channel layout below and the
> two-layer overlays are the target the encoder (FMC-WS-2) implements against. Byte-exact offsets are
> implementation detail (computed from numpy struct dtypes, as today); this doc fixes the *shape*.
>
> **This doc is the single authority on channel content.** Implementation plans defer to it.

## Two messages

The standard stream is two message types over the existing WebSocket, mirroring LSL's
`StreamInfo` + timestamped-`push_sample` model:

| Message | Cadence | Encoding | Evolves from |
|---|---|---|---|
| `stream_schema` | once on connect, + on change | JSON | `TrackerSchemasMessage` / `TrackerDefinition` |
| `stream_sample` | one per frame | binary | the binary keypoints protocol + the per-frame *numeric* bits of `FrontendPayload` |

Rule that defines the split: **static facts go in `stream_schema`; only numbers + a timestamp go in
`stream_sample`.** Nothing static is repeated per frame (this removes today's per-frame `embed_names`).

**Two hard rules:**
- **Every sample carries a timestamp** (LSL-like; the primary time key — [01](01-canonical-data-model.md)).
- **Image data stays separate.** Camera frames + frame metadata are a *different* stream (the existing image
  path); the standard stream is the **non-image** skeleton/kinematics data. The two **link by frame number**.

## `stream_schema` (the StreamInfo)

Evolves `TrackerDefinition` (`{name, tracked_points, connections}`) into a full descriptor. One entry
per active stream.

| Field | Source | Notes |
|---|---|---|
| `stream_id` | new | **unique** id (uuid-derived) — the key everything is addressed by |
| `stream_name` | `name` | human-facing label; **not** required to be unique |
| `coordinate_convention` | **new** | `{units, handedness, up_axis, forward_axis, rotation_form}` — see [07](07-coordinate-conventions.md). Canonical = **mm / right-handed / +Z up / +X forward**, quaternions `wxyz`. |
| `channels` | evolves `tracked_points` | the **ordered** channel layout — the heart of the schema (see below) |
| `connections` | `connections` | `(proximal, distal)` pairs for rendering |
| `joint_hierarchy` | **new** | parent → children over **segments** — drives retarget |
| `segment_parents` | **new** | segment → parent segment. With `rest_pose`, this is everything a consumer needs to compose the local-rotation chain into world placement — the VMC/VRM model. |
| `rest_pose` | **new** | per-segment T-pose rest positions **+ reference orientations**; identity == this pose |
| `sample_layout` | **new** | how to parse `stream_sample`: block order, per-block dtype + column count |

> **Stream dimensions are fixed at creation; rebuild on change.** Subject count (**max persons = 1** for now)
> and camera count (# connected cameras, for `OVERLAY_2D`) are set when the stream/schema is created. A topology
> change (camera add/remove, subject count) **tears down and rebuilds** the stream with a new schema — the
> schema-on-change rule. Samples still carry `subject_id` / `camera_id`; the vector *width* is constant for a
> stream's life. Nothing is padded or excluded. See
> [01 — multi-subject](01-canonical-data-model.md#multi-subject-from-day-one).

### `channels`

> **This section is the single authority on channel content.** Implementation plans (including
> [`phase-1/03`](phase-1/03-canonical-frame-extensions.md)) implement against it and must not carry a
> competing definition. Terms — *keypoint* / *landmark* / *segment* — are defined in
> [13](13-tracker-to-canonical-mapping.md#two-kinds-of-trajectory).

An ordered list of channel groups; the sample body is these groups concatenated in this order, so the
decoder needs no per-frame names.

**Two things are on the wire: what the tracker measured, and the segment model reconstructed from it.**

| # | Group | Names are | Columns | Source |
|---|---|---|---|---|
| 0 | `KEYPOINTS_3D` | tracker keypoint names | `x, y, z, reprojection_error` | triangulated detections (SkellyTracker) |
| 1 | `SEGMENT_ORIGINS` | segment names | `x, y, z` | fitted segment model (SkellyForge) |
| 2 | `ROTATIONS_LOCAL` | segment names | `w, x, y, z` | orientation solver |
| 3 | `ROTATIONS_WORLD` | segment names | `w, x, y, z` | orientation solver |
| 4 | `DERIVED_POINTS` | `center_of_mass`, `xcom` | `x, y, z` | whole-body kinematics |
| 5… | `OVERLAY_2D` | see [2D overlays](#2d-overlays-detections-and-reprojections) | `x, y, visibility` | per camera, two layers |

**`KEYPOINTS_3D`** is the measured half: triangulated tracker detections, tracker-named. It is what the
cameras saw, before any model was fitted to it.

**`SEGMENT_ORIGINS` + the rotation groups** are the reconstructed half — the 3D segment model. Together
they fully describe the fitted skeleton: where each segment's transform sits, and how it is oriented.

- A **segment origin** is the segment's **transform origin — its proximal joint position**, not the
  segment's midpoint. This is deliberate: it is exactly what a VRM/VMC bone transform's position *is*, so
  the mapping to VMC needs no conversion. See [VMC shape](#why-this-shape-maps-onto-vmc).
- No `reprojection_error` column — a segment origin is fitted, not triangulated. Fit quality is visible
  through the reprojection overlay layer, which is the honest measure of it.

**Landmarks are not on the stream.** A landmark (a named anatomical feature riding on a segment) is a
concept the model layer will grow into; it is **`[LATER]`, possibly never on the wire**. Right now the
segment model *is* the reconstructed data, and adding a third point set before it is needed would be
speculative wire surface. Terms per
[13](13-tracker-to-canonical-mapping.md#two-kinds-of-trajectory).

Notes on the remaining groups:

- **Rotation groups** carry `wxyz` quaternions, identity == T-pose, per
  [07 § Segment rotation conventions](07-coordinate-conventions.md#segment-rotation-conventions). **Both
  frames are first-class**, per locked decision 5 — adapters take what their target needs (VMC takes local;
  world-space analysis and the 3JS renderer take world), and world is one multiply from local so carrying
  both costs nothing to produce. Both are always declared so the wire shape is stable; unresolved segments
  are NaN per the [missing-data rule](#missing-data).
- **`reprojection_error`** is named for what it is; never a naked "confidence".
- **`DERIVED_POINTS`** are *points*, not "scalars" — there is no SCALARS kind. Migrated off the JSON
  payload into the binary sample.

#### Why this shape maps onto VMC

VMC's model is a **root transform (position + rotation) plus per-bone local rotations** — child bones carry
no position of their own; their placement comes from the rig's rest pose composed with the local rotation
chain. Every choice above is made so that mapping is a rename, not a computation:

| VMC needs | We ship | Conversion |
|---|---|---|
| root bone position | `SEGMENT_ORIGINS[root]` — a transform origin, already | axis/unit convert only |
| per-bone local rotation | `ROTATIONS_LOCAL` | axis/handedness convert, `wxyz` → target order |
| rest pose (identity reference) | `rest_pose` in the schema, identity == T-pose | declared, not re-derived |
| bone names | segment names + the VRM alias table | `resolve_alias()` |

That is the whole VMC adapter: a name map and a convention conversion. Nothing has to be reconstructed at
the adapter, which is the property the whole layer exists to buy
([00](00-overview.md#the-bet-one-standard-stream-many-transports)).

Non-root segment origins are still carried — they are what the viewport draws, what analysis consumers
want, and what makes the stream useful without a rig on the other end. VMC simply ignores them.

#### 2D overlays: detections *and* reprojections

Each camera's overlay carries **two layers**, so fit quality is directly visible per camera:

| Layer | Names are | What it shows |
|---|---|---|
| detections | tracker keypoint names | what the detector actually saw in that camera's image |
| reprojections | segment names | the fitted segment model projected back down into that camera |

Overlaying them makes the residual between observation and fit visible per camera, per frame — the
cheapest validation instrument the pipeline has, at negligible wire cost.

**Reprojection uses the existing camera calibration.** If we are reconstructing 3D, we know the camera
intrinsics and extrinsics by definition; reprojection reads the same calibration the triangulator consumes.
A calibration change invalidates the reprojection layer exactly as it invalidates triangulation, and the
stream is rebuilt with a new schema per the schema-on-change rule.

Camera *images* remain a separate stream, linked by frame number.

## `stream_sample` (the per-frame binary)

Evolves the binary keypoints protocol. Same framing discipline (header + blocks + footer, contiguous,
little-endian, `float32` wire dtype), with these **additions/removals**:

```
SAMPLE_HEADER
    message_type      u1
    timestamp         f8    ← NEW, first-class (today: multiframe_timestamp, off the binary)
    frame_number      i8
    subject_id        …     ← NEW (multi-subject; keying TBD)
    num_blocks        u4

For each block (in schema `sample_layout` order):
  BLOCK_HEADER
    message_type      u1
    block_kind        u1    ← KEYPOINTS_3D | SEGMENT_ORIGINS | ROTATIONS_LOCAL
                    │         | ROTATIONS_WORLD | DERIVED_POINTS | OVERLAY_2D
    dtype_code        u1    = FLOAT32
    cols              u1    ← cols/element (keypoints [x,y,z,reprojection_error];
                    │         origins/derived [x,y,z]; rotations [w,x,y,z]; overlay_2d [x,y,visibility])
    camera_id         S16   ← empty unless OVERLAY_2D
    overlay_layer     u1    ← empty unless OVERLAY_2D: DETECTIONS | REPROJECTIONS
    num_elements      u4
    data_byte_length  u4
  BLOCK_DATA          row-major [num_elements × cols] float32   ← NO embedded names (schema-backed)

SAMPLE_FOOTER            mirrors SAMPLE_HEADER (integrity check, as today)
```

**One `block_kind` per channel group** — no generic `ROTATIONS` kind; a rotation that doesn't declare its
frame is precisely the ambiguity [07](07-coordinate-conventions.md#the-local-rotation-trap-vmc-and-unreal)
warns about. Overlay blocks are keyed by `(camera_id, overlay_layer)`, so a 3-camera rig sends 6 overlay
blocks per sample.

### Missing data

A point/segment absent this frame → its row is `NaN`, confidence `0` (this is exactly today's rule for
non-triangulated points; it now also covers not-yet-populated rotation channels).

## Mapping to LSL (why the shape is what it is)

The whole point of this layout is a mechanical LSL bridge:
- `stream_schema` → an LSL **`StreamInfo`**: `channel_count` = total columns across groups;
  `channel_format` = float32; per-channel labels/units/convention → the `StreamInfo` XML description;
  `nominal_srate` from the pipeline rate (or `IRREGULAR`).
- `stream_sample` → **`push_sample`**: flatten the blocks (already in schema order) into one float
  vector; pass `timestamp` straight through as the LSL sample timestamp.

No translation step — the LSL route reads the same schema + samples the UI does. See
[03 — The LSL route](03-emitters.md#the-lsl-route).

## Evolution from the current code (what changes)

| Today | Becomes | Change |
|---|---|---|
| `TrackerDefinition` | `stream_schema` entry | + convention, hierarchy, rest pose, channel layout, rotation channels, subjects |
| `TrackerSchemasMessage` | `stream_schema` message | still schema-first; richer payload |
| binary keypoints blocks (`KEYPOINTS_3D`/`SKELETON_3D`, `embed_names`) | `stream_sample` blocks, one kind per group | + timestamp + subject; **drop `embed_names`** (names in schema); the rigidified skeleton becomes `SEGMENT_ORIGINS`; + rotation + `reprojection_error` channels |
| `FrontendPayload` (CoM, xcom in JSON) | a `DERIVED_POINTS` block | per-frame 3D points move off JSON into the binary sample |
| `FrontendPayload` 2D overlays (per camera) | `OVERLAY_2D` blocks **in the stream**, two layers per camera | detections + reprojected segment model (camera *images* stay separate) |
| `body_kinematics` (always `None`) | *(dropped)* | disabled/dead — [01 live-substrate-only](01-canonical-data-model.md#live-substrate-only) |

## Open questions

- **`nominal_srate`**: regular vs. irregular for the LSL `StreamInfo`. `TBD` — trigger: measure the
  realtime pipeline's actual frame-interval jitter. If it is regular enough to declare a rate, LSL
  consumers get better clock handling; if not, `IRREGULAR` is the honest value.

**Resolved and moved into the body of this doc** (kept here as a pointer so the history is legible):
2D overlays are in the stream with two layers per camera ([above](#2d-overlays-detections-and-reprojections));
rotation channels are always declared, NaN until resolved ([above](#channels)); subject count is **fixed at
stream creation** and *is* in the schema as `max_persons` — a topology change rebuilds the stream, per the
schema-on-change rule ([above](#stream_schema-the-streaminfo)). `subject_id` remains a stable id where the
tracker provides identity, else a slot index
([01](01-canonical-data-model.md#multi-subject-from-day-one)).
