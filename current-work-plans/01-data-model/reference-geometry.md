# Reference Geometry (the rest pose)

**Describes:** `RestPose` + `rest_pose.yaml` — the authored T-pose every live pose is measured
against. Model/authoring format lives in [segment-model.md](segment-model.md); vocabulary in
[../00-foundation/glossary.md](../00-foundation/glossary.md).

## What it is

`RestPose` (`core/skeleton/pose/rest_pose.py`) is the standard human's reference pose:
`rest_pose.yaml` carries **only per-segment rest geometry** — each entry's optional
`orientation` is a parent-relative `[w, x, y, z]` quaternion (defaulting to identity). The
parent/child topology lives in `human_skeleton.yaml`'s `joints:` section (the linkage layer); walking
joints × orientations composes the world transforms. `RestPose.from_yaml` requires an entry for every
segment. Every segment's local `+z` runs proximal → distal, so identity orientation means "continues
straight on from its parent".

## Provenance

The pose was derived against a concrete VRM humanoid: `definitions/human_skeleton/default-vrm.gltf.json5`,
exported from Blender's VRM extension. That file is what to check any change here against — the
orientations are derived from real anatomy positions, not dialled in by eye:

- `clavicle` rotates ~28° posteriorly so the bone runs sternoclavicular → acromion; its child
  compensates so the arm still reaches straight out.
- `upper_arm` maps local `+z` onto world `∓x` (arms out to the sides); the right side is the left
  mirrored across the sagittal plane — for a quaternion, `(w, x, -y, -z)`.
- `upper_leg` is a half turn about x (local `+z`, toward the knee, becomes world `-z`); self-mirroring.
- `foot` −63.86° / `heel` +31.34° about x compose with the leg's half turn so both the ball AND the
  calcaneus sit at the same height — the feet stand on one flat ground plane.
- `toes` a half turn landing them flat and forward; self-mirroring.

## Invariants (`RestPose.from_yaml` enforces all of these)

- An entry exists for **every** segment of the skeleton, and there is exactly **one root** (`pelvis`).
- The parent tree and `connect_at` are validated against the `joints:` topology, not declared here.
- Unknown keys are rejected; nothing is inferred silently.
- The composed geometry satisfies the ground-plane test:
  `test_both_feet_stand_on_one_flat_ground_plane` ties heel orientation, heel length, and foot
  orientation together so none can drift alone.

## Identity-at-T-pose, precisely stated

The old "world AND local identity for every segment" contract does not survive this authoring —
only 3 of 61 segments are fully specified (roll measured). The invariant that replaces it:

> **A fully-specified segment solves to its own authoring frame from its own rest positions**
> (`test_every_fully_specified_segment_solves_to_its_own_authoring_frame`). This keeps the
> Gram-Schmidt reference geometry and the Umeyama/FK local positions one answer to "which way does
> this segment face", not two.

Underspecified segments get their roll from `ContinuousRollResolver`
([../02-pipeline/kinematics-engine.md](../02-pipeline/kinematics-engine.md)), not from measurement —
their live orientation at T-pose equals their transported reference only after roll resolution has
seeded from the rest pose.

## On the wire

`ModelDefinition.from_standard_human(skeleton=..., rest_pose=...)` serializes the rest pose into
every frame message: per-segment `rest_orientation` (wxyz world quats), `length_proportion`, plus
`connections` — the `(parent, child)` name pairs of this tree. See
[message-contract.md](message-contract.md).
