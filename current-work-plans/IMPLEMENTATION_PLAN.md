# Implementation Plan & Progress

> **Live (2026-08-24).** Re-created slim after the Aug 20–24 skellyforge rebuild made the previous
> tracker obsolete; that generation's records live in [`archive/`](archive/). The scope table below
> is the live queue — the progress log is history, newest first.

## Scope table

### `[IN]`

- **Linkage/chain layer** — reconcile the hierarchy currently living in `rest_pose.yaml`'s
  `parent`/`connect_at` fields with the placeholder `SegmentLinkage`/`KinematicChain` classes;
  joint angles come with it; IK seams stay future.
- **Length-estimation cleanup** — live rolling-median lengths are wired in the aggregator (landed
  2026-08-24); owed: delete-or-drive the dead `segment_length_window_s` config field and decide
  inline-mirror vs. calling skellyforge's `estimate_segment_lengths` directly
  ([02-pipeline/segment-length-estimation.md](02-pipeline/segment-length-estimation.md)).
- **Face component implementation** — currently commented out of the composition (`#TODO`);
  `FaceBlendShapes` plumbing exists, the component does not load.
- **Posthoc rebuild** — **deferred by decision**; the offline mocap/calibration paths are
  broken-if-invoked against installed skellyforge (scope +
  [02-pipeline/posthoc-rebuild.md](02-pipeline/posthoc-rebuild.md)). Carries the neutral-naming
  decision (`SkeletonDefinition` → a name a non-human board can wear).

### `[LATER]`

VMC adapter · frontend test suite · HTTP control plane ([03-transport/http-control-plane.md](03-transport/http-control-plane.md)) ·
on-disk tidy serialization ([03-transport/serialization-tidy.md](03-transport/serialization-tidy.md)) ·
LSL / URDF / OpenSim exports.

### `[FUTURE]`

The constraint/solve layer — typed joints, chains/IK, twist-backfill — seams only.

## Dependencies & blockers

| Dependency | Blocks | Trigger that resolves it |
|---|---|---|
| Linkage layer | IK / constraint work | hierarchy reconciled out of `rest_pose.yaml` |
| Posthoc rebuild | tidy serialization | both offline paths run on the new core |

## Progress log

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
