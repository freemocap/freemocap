# Implementation Plan & Progress

> **Live.** The scope table below is the live queue — the progress log is history, newest first.

## Scope table

### `[IN]`

- **Recording contract + posthoc rebuild** — serialize the shared channel model first, then integrate
  restartable stages and explicit keep/overwrite semantics. See the
  [data model](03-transport/recording-data-model-proposal.md) and
  [rebuild plan](02-pipeline/posthoc-rebuild.md). The neutral-naming question is
  **settled**: `SkeletonDefinition` keeps its name, and "skeleton" is the generic term — a board is a
  one-segment skeleton ([ontology.md](ontology.md)).
- **Pelvis split** — deferred from the spine redesign (ownership/cascade got tangled); a
  `left_pelvis`/`right_pelvis` pair under the root pelvis, for better shoulder/SC visuals.
- **Face component implementation** — currently commented out of the composition (`#TODO`);
  `FaceBlendShapes` plumbing exists, the component does not load.
### `[LATER]`

VMC adapter · frontend test suite · HTTP control plane ([03-transport/http-control-plane.md](03-transport/http-control-plane.md)) ·
optional CSV/NPY, Blender and .freemocap.mp4 exporters (after the core recording/stage contract) ·
LSL / URDF / OpenSim exports.

### `[FUTURE]`

Finger coupling ratios — authored per-finger MCP↔PIP↔DIP constraints enforced in synthesis/IK/backfill.

## Dependencies & blockers

| Dependency | Blocks | Trigger that resolves it |
|---|---|---|
| Recording schema + reader/writer round trip | posthoc stage persistence | mixed-rate and keep/overwrite fixtures pass |
| Restartable posthoc core | additional-format exports | stage reuse/invalidation and real recording checks pass |
| skellyforge + skellytracker pushed | freemocap's venv seeing either repo's changes | user commits/pushes both, then `uv sync` freemocap |

## Progress log

- **2026-09-05 (recording foundation)** — Added typed Parquet storage, descriptor validation,
  static channel expansion, checkpoint retention/invalidation, keep/overwrite publication and JSON
  mirror recovery. Added true two-pass batch scale fitting. 22 focused tests pass. Worker/API/playback
  integration and additional-format exporters remain; see the posthoc plan's implementation progress.

- **2026-09-05 (plans only)** — Recorded timestamp-first, group-local sample identity; separate source
  and reference frame; component/value Parquet; explicit integer run keep/overwrite. Planned staged
  posthoc rebuild, dependency invalidation, checkpoint publication and subsequent optional exporters.
  No implementation completion is claimed.

- **2026-08-27 (generic skeletons — the charuco board)** — A charuco board is now a
  `SkeletonDefinition` and reconstructs end to end, with **no board-specific branch anywhere in the
  pipeline**. skellyforge: `LandmarkGroup` + `LandmarkConnectionGroup` carry tags, `ColorPalette`
  (`definitions/color_palette.yaml`) resolves tags to colours, `build_rigid_marker_skeleton` builds a
  one-segment N-landmark skeleton from plain positions, `RestPose.default_for` and
  `CenterOfMassDefinitions.default_for` supply defaults, `derived_quantities` makes everything exotic
  opt-in and fails loud at load, and the scale layer renamed to `model_scale_fitting.py` /
  `SegmentPose.scale_estimate` / `ModelScaleFit.fitted_scale`. The human's skull outline and eye lines
  are authored as groups — the worked example that this is not a board feature. skellytracker:
  `passthrough_keypoints_as_landmarks` (a one-line mapping file, not one line per corner), and the
  board's normalized geometry + grid/quad connection groups derived from cv2 rather than hand-rolled.
  freemocap: `TrackedSkeletonBundle` per tracked thing, `reconstruct_skeleton` as a pure per-skeleton
  function, producers/composer/aggregator looping over bundles, `camera_2d_detections` requiring a
  detector type. The frontend collapsed four singular frame channels (origins / rotations / lengths /
  derived) into ONE plural `models: ResolvedModelFrame[]`; every renderer iterates it; the
  schema-driven `ConnectionRenderer` and `SegmentConnectionRenderer` were both deleted in favour of
  one `ModelConnectionRenderer`, with playback migrated onto the model path
  (`playback-model-frame.ts`) so the whole `schemaState` channel could go. Both name-parsing sites are
  gone. Verified on the wire: one frame carries two models / two instances / two trackers, the 5x3
  board ships 8 charuco corners (green `#14ff14`) + 28 aruco corners (orange `#ff8c14`) + 10 grid
  edges + 28 quad edges, and `fitted_scale_mm` comes back as 54.0 against
  `scale_reference_name: "square_length"` — the entered calibration value, recovered
  ([07-generic-skeletons/design.md](07-generic-skeletons/design.md)).

- **2026-08-26 (body-scale fit)** — The proportional template got a size. Hydration's rigid fit
  became a **similarity** fit (`align_point_sets_similarity`, Umeyama): scale now comes out of the
  same SVD as the rotation, which fixed origins that had collapsed onto the observed centroid
  (`thoracic` was 200mm out against a perfect subject, `pelvis`/`skull` ~54mm). Every `SegmentPose`
  carries a `body_scale_estimate`; `body_scale_fitting.py` pools them into one body height plus a
  per-segment scale field that relaxes to that height where there is no data
  ([02-pipeline/model-scale-fitting.md](02-pipeline/model-scale-fitting.md), renamed from
  `body-scale-fitting.md` by the generic-skeletons work below). Only segments built
  entirely from landmarks the tracker mapping *measures* may set the height — new
  `TrackerMapping.directly_measured_landmark_names` — so constructed trunk landmarks cannot quote
  the template back as evidence. `landmark_world_positions` takes the scale field, fixing a CoM
  that had been computed from landmarks collapsed onto their segment origins.
  `segment_length_estimation.py` deleted (subsumed). Wire: `RestSegment.length_mm` →
  `length_proportion`, `ModelInstance.body_height_mm` added, goldens regenerated; the UI consumes
  both. Config: dead `segment_length_window_s` + `height_mm` + `NOMINAL_SUBJECT_HEIGHT_MM` deleted,
  replaced by the one field that drives the fit (`segment_scale_window_frames`). Verified seated:
  with only the arms voting, the unseen foot fits within 0.2mm of its standing measurement.
  Also fixed two stale tests found in the audit — the tracker-mapping round trip was comparing
  `H`-unit positions against a millimetre tolerance (vacuously green; real worst residual 1.1mm at
  `H = 1700`), and `test_arm_abduction` asserted on an angle between two roll-resolved quaternions
  and named a `chest` segment the spine redesign had deleted.

- **(spine/thorax redesign + proportional authoring)** — Trunk re-partitioned at tracker-solid lines:
  `sacrolumbar` (hip center) → `thoracic` (chest_center → neck_center = shoulder midpoint) →
  `cervical_spine` (neck_center → head center) → `skull`; `neck_center`/`chest_center` replaced the
  old junction landmarks; sternoclavicular joints anteriorly offset; xiphoid kept as thoracic volume
  reference. Tracker mapping ratios regenerated. Landmark coordinates converted from mm to
  **body-height proportions** (`H = 1.0` = floor-to-skull-top); `anatomical_segment` moved from a
  hardcoded Python dict onto each segment's component YAML; bilateral joints authored once via
  `sided: true`. The body-fitting step that scales the template to mm landed the following day.
- **2026-08-24 (spine audit + mapping/model fixes)** — Root-caused the fluffy-spine viewer
  artifact: SkellyTracker's `anatomical_offset` ratios were stale against the shipped rest pose
  (junction errors 16–46mm growing up the chain), two definitions of each junction reached
  consumers (raw mapped vs fitted origin), and `craniocervical_junction` was pinned to the
  trunk frame while the skull tracked the real head. Fixed where each lives: ratios regenerated
  programmatically (`skellyforge/scripts/generate_tracker_mapping_ratios.py`) into both body
  mappings; `craniocervical_junction` re-anchored to the ear mean so the cervical segment
  follows the head; skull ears made symmetric about the origin (mapped `head_center` IS the
  ear mean); drift guarded by
  `skellyforge/tests/test_tracker_mapping_offset_round_trip.py` (explicit allowances for the
  frame-unreachable SC/crest points); pre-existing face-yaml test path repaired. Known-left:
  lumbar/chest remain trunk-frame-driven (no midline keypoints in body7) — the spine cannot
  articulate until a midline source exists.
- **2026-08-24 (docs)** — Plan folder reconciled to code: dead-generation docs archived under
  [`archive/2026-08-24-skellyforge-rebuild/`](archive/2026-08-24-skellyforge-rebuild/) and rewritten
  against the current core (segment-model, reference-geometry, kinematics-engine, realtime-loop,
  segment-length-estimation, glossary); conventions/testing/tracker-mapping/posthoc patches;
  `ModelDefinition.connections` + `SegmentConnectionRenderer` documented; new biomechanics-layer doc;
  this tracker recreated slim. HANDOFF / AUDIT / the two proposals deleted intentionally by the user.
- **2026-08-24 (code, same day)** — live per-subject segment lengths wired: the aggregator records
  observed origin→primary distances in a 30-frame rolling window per segment and publishes the
  median (authored-length fallback until measured); window clears on calibration reload/reset.
  Owed cleanup tracked as `[IN]`: dead `segment_length_window_s` field; inline-mirror vs. direct
  call into skellyforge's estimator.
- **2026-08-20 → 2026-08-24 (code)** — skellyforge rebuilt again: VRM-aligned re-authoring (**61
  segments / 124 landmarks / 52 blendshapes**; `rest_pose.yaml` parent tree + relative quats derived
  against `default-vrm.gltf.json5`), closed-form hydration (`hydrate_skeleton` Kabsch ≥3 pts /
  shortest-arc direction fit) + `ContinuousRollResolver` per-take parallel transport replacing the
  swing+twist/damped tiers; `core/biomechanics/` revived (de Leva parameters, partial-CoM-aware
  segment CoMs, inertia, ground reference); old `skellymodels`/`post_processing`/`data_models`
  deleted upstream; tracker mapping YAMLs moved into skellytracker. freemocap's realtime loop
  re-pointed end to end — ingest conversion, One Euro filter, point gate, mapping-before-hydration,
  roll resolution, reprojection overlay, CoM/XCoM streaming via `DERIVED_POINTS`, `connections` on
  the wire — with the frontend consuming it data-driven (`SegmentConnectionRenderer`).
