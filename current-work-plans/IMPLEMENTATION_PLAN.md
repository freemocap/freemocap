# Implementation Plan & Progress

> **Live (2026-08-17).** The scope table below is the current iteration's queue. The dated progress log
> is history (newest first). Older trackers + specs live under [`archive/`](archive/).

## How to use this document

- The scope table is the live queue for this iteration.
- The progress log records what lands; it is history — current scope lives in the table.

## Scope table — "standard-human ontology rebuild" iteration

The goal: rebuild the skellyforge standard human onto the full seven-layer ontology (keypoint → mapping →
landmark → segment → linkage → chain → skeleton), defined in YAML and compiled into typed objects, then
port the solve onto it and delete the old system.

### `[IN]` — this iteration

- **Ontology classes** — `AnatomicalLandmark` / `RigidBodySegment` / `JointLinkage` /
  `KinematicChain` / `HumanSkeleton` / `StandardHumanTPose` (+ `FaceBlendShapes` for the 52 ARKit
  blendshapes). DONE.
- **YAML definitions** — flat part files (pelvis, axial, arm, hand, leg, foot, face) with sidedness +
  Y-mirroring + `$include` composability. DONE (49 segments authored).
- **Solve/hydration port** — port `orientation_solver.py` + `reference_geometry.py` onto the new
  classes: hydrate landmarks from keypoints, solve the rigid body (Kabsch for 3+ landmarks), derive
  lengths from `rest_position`. The detailed design:
  [solve-hydration-port.md](02-pipeline/solve-hydration-port.md). NEXT.
- **Delete the old system** — after the port, excise `segment_definition.py` / `reference_geometry.py` /
  the old `StandardHuman` / `rest_pose.py` machinery.

### `[LATER]`

- **Charuco revival** — charuco board tracking → the standard-human model → display (2D + 3D).
- **Posthoc parity** — rebuild the posthoc mocap pipeline onto the new model (realtime + posthoc share one
  model / solver).
- **VMC adapter** — project the skeleton outward over VMC.
- **Frontend test suite** — plan + build specifically for the current system (not a vestigial holdover).
- LSL adapter; URDF / OpenSim / blendshape exports; VRChat OSC.

### `[FUTURE]`

- The constraint/solve layer — typed joints, chains/IK, twist-backfill — seams only, per
  [ontology.md](ontology.md).

## Dependencies & blockers

| Dependency | Blocks | Trigger that resolves it |
|---|---|---|
| Solve/hydration port | delete the old system | Port `orientation_solver.py` + `reference_geometry.py` onto `RigidBodySegment`/\`AnatomicalLandmark` |

## Progress log

- **2026-08-17 (standard-human ontology rebuild — classes + YAML landed).** Rebuilt the skellyforge
  standard human onto the seven-layer ontology: `AnatomicalLandmark` / `RigidBodySegment` /
  `JointLinkage` / `KinematicChain` / `HumanSkeleton` / `FaceBlendShapes` with `from_yaml`
  loaders, typed config (`cls(**data)`, no string-key indexing), `$include` composability, and
  sidedness via `sided: true` parts instantiated left/right with Y-mirroring. Authored the full
  standard human as flat part files (pelvis, axial, arm, hand, leg, foot, face) — 49 segments / 48
  linkages / 15 chains, audited green (one root, unique names, linkages == segments − 1, right-side
  mirrored, shared landmarks resolved by name agreement, lengths derived from `rest_position`). The face
  is 52 ARKit blendshapes (eyes/ears/nose are LANDMARKS on the skull, not segments). NEXT: the
  solve/hydration port, then delete the old system.
- **2026-08-17 (milestone — the full end-to-end loop works).** Cameras → keypoints → mapping → length +
  fit → orientation solve → self-describing frame message → transport → decode → 3D rigid-body render.
  The message-model swap landed (five kinds, fully self-describing frame).
  Docs reconciled; prior spec set archived under
  `archive/2026-08-17-message-model-cutover/`.
