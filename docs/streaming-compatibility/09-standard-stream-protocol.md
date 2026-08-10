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
| `stream_sample` | one per frame | binary | the binary keypoints protocol + the per-frame bits of `FrontendPayload` | #TODO NOTE - Lets keep the image data (frames and frame metadata) separate from teh non-image data - they link through frame number - ALSO - NOTE MUST ALWAYS INCLUDE A TIMESTAMP, LSL-like protocol 

Rule that defines the split: **static facts go in `stream_schema`; only numbers + a timestamp go in
`stream_sample`.** Nothing static is repeated per frame (this removes today's per-frame `embed_names`).

## `stream_schema` (the StreamInfo)

Evolves `TrackerDefinition` (`{name, tracked_points, connections}`) into a full descriptor. One entry
per active stream.

| Field | Source | Notes |
|---|---|---|
| `stream_name` / `stream_id` | new / `name` | identifies the stream | #TODO NOTE - need clarify - are id/name the same thing? maybe id can be a uuid derived unique id and name could be something isnt necessarilty unique? need discussed
| `coordinate_convention` | **new** | `{units, handedness, up_axis, forward_axis, rotation_frame, rotation_form}` — see [07](07-coordinate-conventions.md). Canonical = mm / right / +Z. |
| `channels` | evolves `tracked_points` | the **ordered** channel layout — the heart of the schema (see below) |
| `connections` | `connections` | `(proximal, distal)` pairs for rendering |
| `joint_hierarchy` | **new** | parent → children, from `AnatomicalStructure` — drives retarget |
| `rest_pose` | **new** | per-segment T-pose rest positions **+ reference orientations**; identity == this pose |
| `subjects` | **new** | subject-dimension declaration (count / keying) — see [01](01-canonical-data-model.md#multi-subject-from-day-one) | #TODO NOTE - I dont get this... what would this look like in practice for the static schema? i dont know wtf you mean by count/keying?) 
| `sample_layout` | **new** | how to parse `stream_sample`: block order, per-block dtype + column count |

### `channels`

An ordered list of channel groups; the sample body is these groups concatenated in this order (so the
decoder needs no per-frame names). Groups:

- **`points`** — named 3D keypoints/landmarks. Columns: `x, y, z, confidence` (generalizes today's
  4th "visibility" column). Names come from here, not per-frame.
- **`rotations`** — named per-segment quaternions. Columns: `x, y, z, w`. **Declared even before the
  SkellyModels code lands** (`TBD` — trigger: incoming code #TODO NOTE - what do you mean? what skellymodels code are you waiting to land?? we have all the info we need now, now that we've seen the bs/ kinematics data an dproperly checked the skellytracker mapping implementation etc stuff#); until populated, samples carry NaN for
  these channels per the [missing-data rule](#missing-data).
- **`scalars`** — low-density per-frame values that live on the frame today in `FrontendPayload`:
  `center_of_mass`, `xcom` (and future kinematics). Migrated off JSON into the sample.

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
    block_kind        u1    ← POINTS | ROTATIONS | SCALARS (replaces KEYPOINTS_3D/SKELETON_3D split)
    dtype_code        u1    = FLOAT32
    cols              u1    ← columns per element (4 for points [x,y,z,conf]; 4 for rotations [x,y,z,w])
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
| `FrontendPayload` 2D overlays | *(unchanged, separate)* | image-overlay render aids stay out of the core standard stream — see Open questions |
| `body_kinematics` (always `None`) | *(dropped)* | disabled/dead — [01 live-substrate-only](01-canonical-data-model.md#live-substrate-only) |

## Open questions

- **2D overlays** (`charuco_overlays` / `skeleton_overlays`): keep them as a separate render-aid message,
  or fold into the schema/sample model? `TBD` (trigger: contract review). Leaning separate — they're a
  UI render concern, not stream data.
- **Subject keying**: `subject_id` type — stable id vs. slot index — `TBD` (trigger: multi-subject
  tracking design), per [01](01-canonical-data-model.md#multi-subject-from-day-one).
- **Rotation channel presence**: are rotation channels always declared (NaN until populated), or omitted
  from the schema until the SkellyModels code lands? Leaning always-declared so the wire shape is stable.
  `TBD` (trigger: incoming SkellyModels code).
- **`nominal_srate`**: regular vs. irregular for the LSL `StreamInfo`. `TBD`.
