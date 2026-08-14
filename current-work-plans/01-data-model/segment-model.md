# Segment Model

> **Scaffold (2026-08-14) — pending ontology revision.** Structure + current facts fixed; full prose is
> authored **after the human-model ontology discussion** (segments / the "rigidifier" framing are being
> revised).

**Describes:** `skellyforge/skellymodels/standard_human/` — `segment_definition.py`, `segment_parts.py`,
`body_part.py`, `hand_part.py`, `face_part.py`, `standard_human_model.py`.
**Salvage:** [`archive/phase-1-work-plans/09-segment-model.md`](../archive/phase-1-work-plans/09-segment-model.md),
[`archive/streaming-compatibility-specs/12-standard-human-model.md`](../archive/streaming-compatibility-specs/12-standard-human-model.md).

## What this covers
The canonical, VRM-1.0-aligned human as a composed set of rigid-body **segments**, each defined
**directly from tracker keypoints** — origin + orientation + length, no landmark layer.

## Key facts (committed code)
- **`SegmentDefinition`** = `name`, `parent`, `parent_attachment` (`ORIGIN`/`DISTAL`), `rigid_points`,
  `origin_keypoint`, `axes`, `rest_rotation`, `rest_roll`†, `length_ratio`, `rotation_limits?`.
- **`AxisDefinition(axis: Literal["x","y","z"], kind: EXACT|APPROXIMATE, target_keypoint)`** — name-driven
  (exact may sit on any of x/y/z), direction `= positions[target] − positions[origin]`, target ∈ rigid_points.
- **Authoring convention:** body/hand exact on **y** (+Y toward child); face exact on **z** (+Z gaze).
- **Composition:** midline (6) + limb ×2 (7 each = 14) + hand ×2 (16 each = 32) + face (8) = **60**;
  `required_keypoints()` = **76**.
- **Head** = 7-point skull clique (`head_center`, `head_vertex`, `nose`, eyes, ears); jaw + mouth corners
  articulate (not in the clique).
- Frozen dataclasses, fail-loud `__post_init__` validators; dict-backed name→segment + parent→children
  indices built once.
- † **`rest_roll` is dead** (authored `0.0`, read nowhere) — C1 in the plan removes it.

## Reconciliation notes
Kill any `long_axis_keypoint`/`twist_keypoint`/`from_keypoint`/`to_keypoint`, "landmark", "55/72". The
face-segment ontology (eyes/mouths targeting `nose`) is under review — hold detailed face prose for the
ontology pass.
