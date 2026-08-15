# Segment Model

**Describes:** `skellyforge/skellymodels/standard_human/` — `segment_definition.py`, `segment_parts.py`,
`body_part.py`, `hand_part.py`, `face_part.py`, `standard_human_model.py`.
**Salvage:** [`archive/phase-1-work-plans/09-segment-model.md`](../archive/phase-1-work-plans/09-segment-model.md),
[`archive/streaming-compatibility-specs/12-standard-human-model.md`](../archive/streaming-compatibility-specs/12-standard-human-model.md).

## What this covers

The canonical, VRM-1.0-aligned human as a composed set of rigid-body **segments**, each defined **from
hydrated landmarks** — origin + orientation + length. A segment is declared by its **landmarks** (the
points rigid on it), an **origin landmark**, and **tagged axis declarations** built from those landmarks;
the per-frame world positions of the landmarks (hydrated through the tracker mapping, or absent =
occlusion) drive the solve. *(The retired thing was the old vague "landmark **layer**" — a separate
fitted-point stage. The precise landmark is alive and is the atom of the model, per
[the ontology](../ontology.md).)*

## Key facts (committed code)

- **`SegmentDefinition`** = `name`, `parent`, `parent_attachment` (`ORIGIN`/`DISTAL`), `landmarks`,
  `origin_landmark`, `axes`, `rest_rotation`, `length_ratio`, `rotation_limits?`, `rigid_with_parent?`.
- **`rigid_with_parent: bool = False`** — declares a **rigid child** (see the
  [glossary](../00-foundation/glossary.md)): the segment's pose is never solved from its own hydrated
  landmarks; it inherits the parent's solved pose composed with its authored rest local rotation.
  **Load-time validation (fail-loud):** every landmark of a rigid child must be a member of its parent's
  `landmarks` — a rigid child whose geometry escapes the parent's rigid set is an authoring error and
  raises. Declared, never inferred.
- **`AxisDefinition(axis: Literal["x","y","z"], kind: EXACT|APPROXIMATE, target_landmark)`** — name-driven:
  the EXACT axis may sit on any of x/y/z (no positional rules); the direction is
  `positions[target_landmark] − positions[origin_landmark]`; **every axis target must be a member of the
  segment's own `landmarks`** (enforced at load — a segment's frame is a function of its own rigid
  geometry only, never an external reference).
- **Authoring convention (VRM 1.0):** body/hand segments declare the EXACT axis on **y** (+Y toward the
  child bone); face segments on **z** (+Z = gaze). The machinery is axis-name-agnostic; the convention
  lives in the authored data.
- **Composition:** midline (6) + limb ×2 (7 each = 14) + hand ×2 (16 each = 32) + face (8) = **60
  segments**; `required_landmarks()` = **76**. Counts are single-sourced in the
  [glossary](../../current-work-plans/00-foundation/glossary.md).
- **Head** = the 7-point skull clique (`head_center`, `head_vertex`, `nose`, left/right eyes, left/right
  ears); `jaw` + the mouth corners articulate (not in the clique). The face-detail segments split the
  same way: **eyes / ears / nose are rigid children of the head** (their landmarks are all skull-clique
  members); **jaw / mouth corners articulate** and anchor at observed.
- Frozen dataclasses, fail-loud `__post_init__` validators (origin ∈ landmarks, every axis target ∈
  landmarks, distinct names, finite `length_ratio`); dict-backed name→segment + parent→children indices
  built once.
- `rotation_limits` is **declared, not yet enforced** (the future constraint layer will read it).

## Graded capability

A rigid body is a point set with fixed pairwise distances; a 2-point segment is the degenerate case.

- **2 landmarks (simple):** origin + exact axis directly; the roll is **not resolved** by the segment's
  own geometry — the critically-damped minimal roll carries it.
- **3+ landmarks (complex):** full 6-DOF via the MDS-template + rotation-only Procrustes fit (see
  [02-pipeline/kinematics-engine.md](../02-pipeline/kinematics-engine.md)).
- **Rigid child (declared):** no independent solve — inherits the parent's solved pose composed with its
  rest local rotation. The grade is authored, not derived: `rigid_with_parent` with the landmark-
  containment validation above.

*(Decision 2026-08-14: the per-segment observed/unobserved-DOF **flag** was dropped — the grade is the
seam and is visible directly from the hydrated-landmark count on the stream. See the
[ontology](../ontology.md) constitution.)*

## Reconciliation notes

Kill any `long_axis_keypoint`/`twist_keypoint`/`from_keypoint`/`to_keypoint`, `rigid_points`,
`origin_keypoint`, `target_keypoint`, `required_keypoints()` — all renamed by the landmark sweep
(`landmarks`, `origin_landmark`, `target_landmark`, `required_landmarks()`). `rest_roll` is removed
(dead field — authored 0.0 everywhere, read nowhere).
