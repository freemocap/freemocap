# 09 — Standard Stream Protocol (the contract)

> The precise wire contract for the standard stream. [01](01-canonical-data-model.md) gives the
> *concepts* (schema vs. sample, what the frame carries); this doc pins the *fields and layout* that
> the backend encoder, the UI decoder, and the LSL route all implement against. It is written as an
> **evolution of the code that already exists**, not a greenfield format.
>
> Status: **draft contract for review.** Byte-exact offsets are implementation detail (computed from
> numpy struct dtypes, as today); this doc fixes the *shape*.

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
| `coordinate_convention` | **new** | `{units, handedness, up_axis, forward_axis, rotation_frame, rotation_form}` — see [07](07-coordinate-conventions.md). Canonical = mm / right / +Z. |
| `channels` | evolves `tracked_points` | the **ordered** channel layout — the heart of the schema (see below) |
| `connections` | `connections` | `(proximal, distal)` pairs for rendering |
| `joint_hierarchy` | **new** | parent → children, from `AnatomicalStructure` — drives retarget |
| `rest_pose` | **new** | per-segment T-pose rest positions **+ reference orientations**; identity == this pose |
| `sample_layout` | **new** | how to parse `stream_sample`: block order, per-block dtype + column count |

> **Subjects are not a schema field.** The schema describes **one** subject's layout; each `stream_sample` is
> tagged with a `subject_id` and the subject count is **dynamic** (discovered from samples) — so multi-person
> needs no schema change. See [01 — multi-subject](01-canonical-data-model.md#multi-subject-from-day-one).

### `channels`

An ordered list of channel groups; the sample body is these groups concatenated in this order (so the
decoder needs no per-frame names). Groups:

- **`points`** — named 3D landmarks. Columns: `x, y, z, reprojection_error` (3D quality — named, never a naked
  "confidence"). Names come from the schema, not per-frame.
- **`rotations`** — named per-segment quaternions. Columns: `w, x, y, z` (w-first, matching the `bs/`
  engine's convention; adapters reorder as their target needs). Produced by the folded-in kinematics engine
  ([11](11-kinematics-fold-in.md)) — **no external code to wait on**. Always declared in the schema so the
  wire shape is stable; NaN per the [missing-data rule](#missing-data) for any segment unresolved this frame.
- **`scalars`** — low-density per-frame values that live on the frame today in `FrontendPayload`:
  `center_of_mass`, `xcom` (and future kinematics). Migrated off JSON into the sample.
- **`overlays_2d`** — the per-camera 2D projection of the tracked landmarks (`x, y, visibility`), **one block
  per camera** (keyed by `camera_id`). Matches the 3D data, 2D-only. Camera *images* stay a separate stream.

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
    block_kind        u1    ← POINTS | ROTATIONS | SCALARS | OVERLAY_2D
    dtype_code        u1    = FLOAT32
    cols              u1    ← cols/element (points [x,y,z,reprojection_error]; rotations [w,x,y,z]; overlay_2d [x,y,visibility])
    camera_id         S16    ← empty unless OVERLAY_2D
    num_elements      u4
    data_byte_length  u4
  BLOCK_DATA          row-major [num_elements × cols] float32   ← NO embedded names (schema-backed)

SAMPLE_FOOTER            mirrors SAMPLE_HEADER (integrity check, as today)
```

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
| binary keypoints blocks (`KEYPOINTS_3D`/`SKELETON_3D`, `embed_names`) | `stream_sample` blocks (`POINTS`/`ROTATIONS`/`SCALARS`) | + timestamp + subject; **drop `embed_names`** (names in schema); + rotation/confidence channels |
| `FrontendPayload` (CoM, xcom in JSON) | `SCALARS` block in the sample | per-frame numbers move off JSON into the binary sample |
| `FrontendPayload` 2D overlays (per camera) | `OVERLAY_2D` blocks **in the stream** | per-camera 2D projection matching the 3D data (camera *images* stay separate) |
| `body_kinematics` (always `None`) | *(dropped)* | disabled/dead — [01 live-substrate-only](01-canonical-data-model.md#live-substrate-only) |

## Open questions

- **2D overlays (resolved):** **in the stream** as per-camera `OVERLAY_2D` blocks (`x, y, visibility`),
  matching the 3D data. Camera *images* stay a separate stream (linked by frame number).
- **Subject keying**: `subject_id` = stable id where the tracker gives identity, else slot index
  (per [01](01-canonical-data-model.md#multi-subject-from-day-one)); count is dynamic, not in the schema.
- **Rotation channels are always declared** in the schema (NaN until resolved) so the wire shape is stable —
  produced by the folded-in engine ([11](11-kinematics-fold-in.md)); nothing to wait on.
- **`nominal_srate`**: regular vs. irregular for the LSL `StreamInfo`. `TBD`.
