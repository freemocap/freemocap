# 10 — Serialization & Tidy Data Format

> The **on-disk** form of the standard human / kinematics data. Sister to
> [09 — Standard Stream Protocol](09-standard-stream-protocol.md) (the *wire* form): both are
> serializations of the same canonical model. This doc compares the two formats that exist
> today and recommends a direction.
>
> Status: **analysis + recommendation for review.**

## Two on-disk formats exist today

### A. SkellyForge parquet (`Actor.create_summary_dataframe`)

`skellyforge/skellymodels/managers/actor.py` writes `freemocap_data_by_frame.parquet`, one row per
`(frame, keypoint, trajectory)`:

| Column | Notes |
|---|---|
| `frame`, `keypoint` | |
| `x`, `y`, `z` | **wide** — three fixed columns |
| `model` | `"{tracker}.{aspect}"`, e.g. `mediapipe.body` — **requires string parsing** |
| `trajectory` | `3d_xyz`, `rigid_3d_xyz`, … |
| `reprojection_error` | |

Pain points (the ones you flagged): the `x/y/z` **wide** columns can't hold a 4-component quaternion
or an angular quantity without a schema change; the `model` column (and the `{aspect}.{trajectory}.{landmark}`
marker ids in the array path) **encode hierarchy in dotted strings that must be parsed**; there's no
first-class `units`; static + dynamic are mixed in one file (model_info rides in `df.attrs`).

### B. `bs/kinematics_core` tidy CSV + reference-geometry JSON

`clients/bs/python_code/kinematics_core/kinematics_serialization.py` writes **two files**:

- `{name}_reference_geometry.json` — **static**: `units`, a `coordinate_frame` (origin + two axes
  defined by keypoints, third by right-handed cross product), and `keypoints` (rest-pose local
  positions). This is a rest pose + body frame. (`ReferenceGeometry`, JSON via Pydantic.)
- `{name}_kinematics.csv` — **dynamic**, fully tidy, one row per `(frame, trajectory, component)`:

  | Column | Notes |
  |---|---|
  | `frame` | int |
  | `timestamp_s` | float — **first-class timestamp** |
  | `trajectory` | `position`, `orientation`, `linear_velocity`, `angular_velocity_local`, `keypoint__{name}`, … (Categorical) |
  | `component` | `x/y/z/w`, `roll/pitch/yaw` (Categorical) |
  | `value` | float |
  | `units` | `mm`, `mm_s`, `mm_s2`, `rad_s`, `rad_s2`, `quaternion` — **first-class** (Categorical) |

## Why the tidy format is better

- **Uniform across dimensionality.** Because `component` is a *column*, the same schema holds
  3-vectors, **4-component quaternions**, and euler triples — no wide-column change. This is the
  decisive win for a format that must carry rotations.
- **Self-describing units** per row (Categorical → cheap).
- **Static/dynamic split** (JSON geometry + tidy CSV) — the same schema-vs-samples split as
  [09](09-standard-stream-protocol.md). The reference-geometry JSON *is* an on-disk schema.
- **No dotted-string parsing** to recover structure. (bs/'s one wart — the `keypoint__{name}` prefix inside
  `trajectory` — we fix below with an explicit **`entity`** column; and it's a **landmark** (canonical), not a
  tracker keypoint.)
- Categorical dtypes keep the long format compact under parquet compression.

## Extending bs/ (single-body) to the whole human

`bs/kinematics_core`'s serialization is **single-rigid-body** — one file per body. A full human is *many*
rigid bodies (one per segment) + the landmark set, possibly multiple people. Extend the tidy schema with
explicit columns (and make the timestamp primary):

- **`timestamp_s`** primary; **`frame`** secondary/nullable (mixed frame-rate sensors).
- **`subject`** (multi-person) and **`entity`** (the **landmark** or **segment** name, e.g. `left_elbow`,
  `upperArm`) — explicit columns, replacing bs/'s `keypoint__{name}` prefix. `trajectory` becomes the
  **quantity** (position / orientation / velocity …).
- carry the **superset** ([01](01-canonical-data-model.md)): landmark positions **+** per-segment
  orientations **+** quality (confidence / reprojection error) — the same superset the stream carries, as rows
  rather than channels. *(Discussion: all of it on disk by default, or selectable?)*

## Recommendation

**Keep the parquet *file*; migrate its *schema* to the tidy-long format** (extended with `subject` / `entity`
columns), retiring the current SkellyForge parquet layout (zero backwards-compat — one format). bs/ used CSV;
we keep **parquet** for compression of the long format, with a **JSON static sidecar** carrying the schema
(names, hierarchy, rest pose, convention).

**On the wire↔disk relationship (corrected):** there is **one canonical model**; its *static* description and
its *per-frame* data are **two axes**, and each can be serialized for the wire or for disk — the wire/disk
split is **not** the same as the static/dynamic split:

| | Static (schema) | Per-frame (data) |
|---|---|---|
| **Wire** (realtime) | `stream_schema` (JSON) | `stream_sample` (binary) — doc 09 |
| **Disk** (posthoc) | JSON static sidecar | tidy-long **parquet** — this doc |

bs/'s `reference_geometry` is a **per-rigid-body** precursor (rest pose + body frame for one body); the
freemocap static description **generalizes** it to the whole-human canonical model, so the disk sidecar is
"the canonical model serialized," of which per-segment reference geometry is a part. *(How far to carry bs/'s
`reference_geometry` shape into that is a discussion item.)*

## Decisions / open

- **Adopt tidy-long (decided):** migrate the parquet **schema** to tidy-long; retire the current SkellyForge
  parquet layout. (Much of the bs/→freemocap adaptation is still to work through.)
- **File format (decided):** **parquet** for the dynamic data + a JSON static sidecar (bs/ used CSV; parquet
  compresses the long format better).
- **Subject/entity dimension (decided):** explicit columns, not string-prefix namespacing.
- **Superset on disk (discuss):** positions + orientations + quality by default, or selectable?
- **`reference_geometry` generalization (discuss):** how far bs/'s single-body reference-geometry shape
  extends to the whole-human static sidecar.
- **Units taxonomy** — pin the canonical set (`mm`, `mm_s`, `rad_s`, `quaternion`, …).
- Relationship to `Trajectory`/`Aspect` in SkellyModels — see [11 — Kinematics Fold-In](11-kinematics-fold-in.md).
