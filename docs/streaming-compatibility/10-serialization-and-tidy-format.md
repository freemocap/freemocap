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

#TODO NOTE - Need consideration - we should drop or downgrade the 'frame' aspect of this thing, in service of a future where we will need to handle info from different frameratede sensors - we dont needt o support ALLL of that, but should gnereally be moving towards a system of a timestamp based something cs a frame number based thing 
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
- **No dotted-string parsing** to recover structure (the one mild exception: the `keypoint__{name}` #TODO NOTE - we need to check in abou tthis part... we want to be consistent with eth keypoint (tracker related) and landmark (cannonical skeleton related) - *think* this wants to be 'landmark___' in this context, right? Also - can you think of a cleaner way to handle this? it might be a vestigial hold over  from the bs code, which was entirely about tracking a single rigid body... we should think about it in this context and discuss to make sure we are getting it clear and right 
  prefix in `trajectory`).
- Categorical dtypes keep the long format compact under parquet compression.

## The gap to close before adopting

`bs/kinematics_core`'s serialization is **single-rigid-body** — one file per body, no subject/segment
dimension. A full human is *many* rigid bodies (one per segment) + the marker set. To serialize the
standard human, the tidy schema needs one more dimension:

- add a **`body` / `segment`** column (and, for multi-person, a **`subject`** column), OR namespace it
  in `trajectory`. Recommendation: explicit columns, not more prefix-parsing.
- carry the **superset** ([01](01-canonical-data-model.md)): marker positions **+** per-segment
  orientations **+** quality (confidence / reprojection error), not just one rigid body's pose. #TODO NOTE - lets discuss this - per above - ngood to talk through and get clear about

## Recommendation

Adopt the **tidy long format + reference-geometry JSON** as the canonical on-disk serialization,
extended with `subject` / `segment` columns, **replacing** the SkellyForge parquet schema (zero
backwards-compat per the repo rule — one format). It is the disk twin of the standard stream:

```
                          SCHEMA (static)                 SAMPLES (dynamic)
   wire (realtime)   →    stream_schema (JSON)            stream_sample (binary)     — doc 09
   disk (posthoc)    →    reference_geometry (JSON)       tidy CSV / parquet         — this doc
```

One canonical model, one schema, two serializations (wire + disk) that share it.

#TODO NOTE - im not 100% sure youve got it right that the stream_schema and reference gemoetyr are matched and differnetiated by the realtime vs posthoc split - again, we should discuss and get clear. Kinda depends how we wantto extend the reference geometry concept from the bs code to the freemocap context maybe? 

## Open decisions

- **Adopt tidy-long as the canonical disk format** (retire the SkellyForge parquet schema)? `TBD`
  (trigger: this review). - #TODO NOTE - yes - adopt tidy-long and retire existing schema - note there's a lot of discussion will need to do to get it apprpriate for the current projct vs bs's needs
- **Subject/segment dimension**: explicit columns vs. trajectory-namespacing. Leaning explicit columns.
- **CSV vs parquet** for the dynamic file (bs/ uses CSV; parquet compresses the long format better).
- **Units taxonomy** (`mm`, `mm_s`, `rad_s`, `quaternion`, …) — pin the canonical set.
- Relationship to `Trajectory`/`Aspect` in SkellyModels — see [11 — Kinematics Fold-In](11-kinematics-fold-in.md).
