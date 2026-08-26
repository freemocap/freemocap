# Implementation Plan & Progress

> **Live.** The scope table below is the live queue — the progress log is history, newest first.

## Scope table

### `[IN]`

- **Body fitting** — the proportional template (`H = 1.0`) needs a fitting step that solves the
  subject's `H` and per-segment proportions from measured distances (hip-to-shoulder as the anchor),
  then scales the template to mm. Formalizes `estimate_segment_lengths` into an explicit H-scaled fit.
- **Tracker mapping proportional conversion** — mapping `reference_length`s are still mm-anchored;
  convert to `H`-proportions alongside the template.
- **Length-estimation cleanup** — delete-or-drive the dead `segment_length_window_s` config field and
  decide inline-mirror vs. calling skellyforge's `estimate_segment_lengths` directly
  ([02-pipeline/segment-length-estimation.md](02-pipeline/segment-length-estimation.md)).
- **Pelvis split** — deferred from the spine redesign (ownership/cascade got tangled); a
  `left_pelvis`/`right_pelvis` pair under the root pelvis, for better shoulder/SC visuals.
- **Face component implementation** — currently commented out of the composition (`#TODO`);
  `FaceBlendShapes` plumbing exists, the component does not load.
- **Posthoc rebuild** — **deferred by decision**; the offline mocap/calibration paths are
  broken-if-invoked against installed skellyforge (scope +
  [02-pipeline/posthoc-rebuild.md](02-pipeline/posthoc-rebuild.md)). Carries the neutral-naming
  decision (`SkeletonDefinition` → a name a non-human board can wear).

### `[LATER]`

VMC adapter · frontend test suite · HTTP control plane ([03-transport/http-control-plane.md](03-transport/http-control-plane.md)) ·
on-disk tidy serialization ([03-transport/serialization-tidy.md](03-transport/serialization-tidy.md)) ·
LSL / URDF / OpenSim exports · charuco-board tracking to force a non-human generic case.

### `[FUTURE]`

Finger coupling ratios — authored per-finger MCP↔PIP↔DIP constraints enforced in synthesis/IK/backfill.

## Dependencies & blockers

| Dependency | Blocks | Trigger that resolves it |
|---|---|---|
| Body fitting | tracker mapping proportional conversion | solve `H` + per-segment proportions from measured distances |
| Posthoc rebuild | tidy serialization | both offline paths run on the new core |

## Progress log

- **(spine/thorax redesign + proportional authoring)** — Trunk re-partitioned at tracker-solid lines:
  `sacrolumbar` (hip center) → `thoracic` (chest_center → neck_center = shoulder midpoint) →
  `cervical_spine` (neck_center → head center) → `skull`; `neck_center`/`chest_center` replaced the
  old junction landmarks; sternoclavicular joints anteriorly offset; xiphoid kept as thoracic volume
  reference. Tracker mapping ratios regenerated. Landmark coordinates converted from mm to
  **body-height proportions** (`H = 1.0` = floor-to-skull-top); `anatomical_segment` moved from a
  hardcoded Python dict onto each segment's component YAML; bilateral joints authored once via
  `sided: true`. The body-fitting step that scales the template to mm is the open `[IN]`.
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
