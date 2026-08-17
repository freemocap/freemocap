# Implementation Plan & Progress

> **Live (2026-08-17).** The scope table below is the current iteration's queue. The dated progress log
> is history (newest first). Older trackers + specs live under [`archive/`](archive/).

## How to use this document

- The scope table is the live queue for this iteration.
- The progress log records what lands; it is history — current scope lives in the table.

## Scope table — "Charuco revival + posthoc parity" iteration

The goal: return the app to its prior functionality (charuco board tracking + the posthoc pipeline) inside
the new architecture, so the old system can be removed entirely. This iteration is scoped to that specific
functionality, not a sprawling refactor.

### `[IN]` — this iteration

- **Charuco revival** — bring charuco board tracking back up: skellytracker's charuco data → the
  standard-human model (skellyforge) → display (2D overlay + 3D). Convert the dormant charuco overlay
  renderer (`charuco-overlay-renderer.ts` + `charuco-types.ts` + the base-renderer
  `ModelInfo`/`AspectInfo`/`Segment` machinery) and the charuco calibration to the self-describing
  system.
- **Posthoc parity** — rebuild the posthoc mocap pipeline onto the new segment model + kinematics:
  realtime (online, per-frame, damped) and posthoc (batch, unbounded window) share one model, one solver,
  one length estimator. The posthoc/calibration path still imports the old skellyforge architecture
  (`skellymodels.managers`, `skellymodels.models`, `data_models.trajectory_3d`,
  `post_processing.*`, `kinematics.segment_lengths`) — this is the seam to close.
- **Remove the old system** — with charuco + posthoc on the new architecture, excise the old skellyforge
  `managers`/`models` layer, the old posthoc imports, and the superseded charuco remnants (the
  `tracker_info/canonical_*.yaml` files die with it).
- **Frontend test suite** — plan + build specifically for the current system (runner choice, golden parity,
  integration), not a vestigial holdover. The swap deleted the old `*.test.ts` files and there is no unit
  runner; this is a clean-slate job.
- **Rotate-once-at-capture** — consolidate the four duplicated `cv2.rotate` sites into one
  rotate-at-capture path (skellycam-scoped), so rotation is applied once and downstream reads the rotated
  space from `rotation` + `image_size`.
- **Fix the reference-skull degeneracy** — the reference skull on disk has degenerate points (eyes
  coincide with `head_center` at rest). A correctly-built skull is not degenerate; fix the reference
  geometry so the skull is non-degenerate.

### `[LATER]`

- **VMC adapter** — project the skeleton outward over VMC (VRM 1.0→0.x names + expressions).
- LSL adapter; URDF / OpenSim / blendshape exports; VRChat OSC.

### `[FUTURE]`

- The constraint/solve layer — typed joints, chains/IK, twist-backfill — seams only, per
  [ontology.md](ontology.md).

## Dependencies & blockers

| Dependency | Blocks | Trigger that resolves it |
|---|---|---|
| Charuco data → standard-human model wiring | charuco revival | Confirm where charuco keypoints hydrate landmarks (skellytracker mapping, not a separate path) |
| Posthoc old-architecture import map | posthoc parity | Enumerate every old-layer import in the posthoc/calibration path |

## Progress log

- **2026-08-17 (milestone — the full end-to-end loop works).** Cameras → keypoints → mapping → length +
  fit → orientation solve → self-describing frame message → transport → decode → 3D rigid-body render.
  The message-model swap landed (five kinds, fully self-describing frame; schema-then-samples + replace-kinds
  retired). 3D render confirmed by the user; backend suites green (user-run); `tsc` clean; docs reconciled
  (removed "code is truth", fixed the stale status + dangling `HANDOFF.md` pointers, rewrote the four
  message-model docs). Prior spec set archived under `archive/2026-08-17-message-model-cutover/`; this
  tracker rebuilt for the next iteration.
