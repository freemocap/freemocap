# Stream Schema + Sample (the data contract)

**Describes (types):** `freemocap/core/streaming/standard_stream/` — `stream_schema.py`,
`stream_sample.py`, `coordinate_convention.py`. The **wire framing / encoder / WS** that carries these
lives in [../03-transport/backend-encoder-ws.md](../03-transport/backend-encoder-ws.md) — this doc owns
the *shapes*, that one owns the *transport*.
**Salvage:** [`archive/streaming-compatibility-specs/01-canonical-data-model.md`](../archive/streaming-compatibility-specs/01-canonical-data-model.md),
[`09-standard-stream-protocol.md`](../archive/streaming-compatibility-specs/09-standard-stream-protocol.md),
[`archive/phase-1-work-plans/01-standard-stream-contract.md`](../archive/phase-1-work-plans/01-standard-stream-contract.md),
[`03-canonical-frame-extensions.md`](../archive/phase-1-work-plans/03-canonical-frame-extensions.md).

## What this covers
The LSL-shaped contract: a **schema** (channels, channel groups, joint hierarchy, T-pose, convention,
units, per-subject dimension) sent once + change, then timestamped **samples** per frame.

## Key facts (committed code)
- Schema is built from the composed `StandardHuman` (`StreamSchema.from_standard_human`), keyed to the
  live camera set; carries **measured segment lengths** with a default-then-update lifecycle (anthropometric
  seeds until the estimators converge).
- **The channel table** — fixed order, one `ChannelGroup` per group (the decoder indexes by position):

  | # | Group | Names | Columns |
  |---|-------|-------|---------|
  | 0 | `KEYPOINTS_3D` | the tracker-named measured keypoints | `x, y, z, reprojection_error` |
  | 1 | `LANDMARKS_3D` | the 76 hydrated landmarks | `x, y, z, reprojection_error` |
  | 2 | `SEGMENT_ORIGINS` | the 60 segment names | `x, y, z` |
  | 3 | `ROTATIONS_LOCAL` | the 60 segment names | `w, x, y, z` |
  | 4 | `ROTATIONS_WORLD` | the 60 segment names | `w, x, y, z` |
  | 5 | `DERIVED_POINTS` | `center_of_mass`, `xcom` | `x, y, z` |
  | 6 | `OVERLAY_2D` | per camera × layer (DETECTIONS / REPROJECTIONS) | `x, y, visibility` |

- **OVERLAY_2D coordinate space** (2026-08-15): values are **capture-resolution image px** (the tracker's
  detections in the camera's image, unscaled), `visibility` carries the tracker's confidence (0–1). The
  schema's **`camera_image_sizes`** (`{camera_id: [width, height]}`) declares each camera's capture size;
  consumers scale overlay points to their own display size with it.

- Samples: binary, `wxyz` rotations, keyed by frame number; golden-byte parity with the TS decoder
  ([../04-ui/ui-integration.md](../04-ui/ui-integration.md)).

## Decision (2026-08-14) — dual channels, settled + landed

The point data travels as **two channels, not one**:

- **`KEYPOINTS_3D`** carries the **tracker-named measured keypoints** — the raw, un-mapped triangulations
  (``message.keypoints_arrays``). The names come from
  `freemocap/core/tasks/mocap/tracker_mappings.py::tracker_keypoint_names(detector_type)` — the
  detectors' own point-name constants (body + ``left_hand_``/``right_hand_``-prefixed hands), so the
  schema and the per-frame keys stay in lockstep. *(Not `TrackerMapping.tracker_names`: offset forms may
  reference landmark names the tracker never emits.)*
- **`LANDMARKS_3D`** carries the **76 hydrated landmarks** — the model-side named points after mapping
  (``message.standard_skeleton``; missing this frame = a NaN row, i.e. occlusion).

Both are first-class consumers of the ontology: keypoints are the measurement, landmarks are the model
points. The schema re-sends when the detector type changes (a pipeline restart with a different
tracker).

## Reconciliation notes
`wxyz`; convention block = the [00-foundation/conventions.md](../00-foundation/conventions.md)
facts, single-sourced (the schema *states* them, doesn't redefine them).
