# Implementation Plan & Progress

> **Live (2026-08-17).** The scope table below is the current iteration's queue. The dated progress log
> is history (newest first). Older trackers + specs live under [`archive/`](archive/).

## How to use this document

- The scope table is the live queue for this iteration.
- The progress log records what lands; it is history — current scope lives in the table.

## Scope table — "serve all three consumers" iteration

The new core is a **boundary object**: one YAML-defined skeleton + one T-pose + one solve, consumed by
three paths. All three must migrate before the old skellyforge system can be deleted:

1. **Realtime** — the live loop. Online, per-frame, damped.
2. **Charuco** — a **non-human rigid body** (the calibration board). The first extension test.
3. **Posthoc** — the recorded loop. Batch, offline, undamped.

They share the model + solver; they differ only in **which model** (human vs. board) and **how time is
handled** (damped vs. batch).

### `[IN]` — this iteration

- **Ontology classes** — `AnatomicalLandmark` / `RigidBodySegment` / `JointLinkage` /
  `KinematicChain` / `HumanSkeleton` / `StandardHumanTPose` (+ `FaceBlendShapes`). DONE.
- **YAML definitions** — flat part files (pelvis, axial, arm, hand, leg, foot, face) with sidedness +
  Y-mirroring + `$include` composability. DONE (49 segments / 48 linkages / 15 chains).
- **Solve/hydration port** — `build_standard_human_tpose` + the re-pointed `solve_frame_orientations`
  (Kabsch for 3+ landmarks, swing+twist for 2, result/state split). DONE (identity-at-T-pose green).
- **Realtime re-point** — re-point the realtime path (`realtime_aggregator_node.py`, `message_model.py`,
  `skeleton_rigidifier.py`, `channel_helpers.py` + producers) to the new API; fix the frontend renderers
  for the renamed segments (49 not 60, `pelvis`, `clavicle`, no `toes`/face segments). NEXT.
- **Charuco re-implementation** — author the board as a YAML skeleton (one rigid segment + marker-corner
  landmarks, `sided: false`) + re-point the charuco path (`charuco_model_from_observations.py`, the
  `Board` actor). Tests the extensibility: the core serves a non-human rigid body.
- **Posthoc alignment** — re-point the posthoc path (`skeleton_from_mediapipe_observations.py`, the
  `Human` actor) to the new loader + solve; share the model + solver with realtime (realtime = damped,
  posthoc = batch).
- **Delete the old system** — only after all three consumers are migrated: excise `segment_definition.py` /
  `reference_geometry.py` / `rest_pose.py` / `body_part.py` / `hand_part.py` / `face_part.py` /
  `standard_human_model.py` + `skellymodels/models/` + `managers/` + `tracker_info/*.yaml`.

### `[LATER]`

- **VMC adapter** — project the skeleton outward over VMC.
- **Frontend test suite** — plan + build specifically for the current system.
- LSL adapter; URDF / OpenSim / blendshape exports; VRChat OSC.

### `[FUTURE]`

- The constraint/solve layer — typed joints, chains/IK, twist-backfill — seams only, per
  [ontology.md](ontology.md).

### Reconsideration the charuco target forces

The core is named human-specific (`HumanSkeleton`, `StandardHumanTPose`), but the board is not a human.
Decide, when charuco lands, whether to neutralize the core names (`Skeleton` / a general rest-pose) so the
human and the board are two instances of the same neutral core.

## Dependencies & blockers

| Dependency | Blocks | Trigger that resolves it |
|---|---|---|
| Realtime re-point | delete the old system | Re-point the realtime path + confirm the live 3D looks correct |
| Charuco + posthoc migration | delete the old system | Both paths load + solve via the new core |

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
