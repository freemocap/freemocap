# Reference Geometry

> **Scaffold (2026-08-14) — pending ontology revision.** Current facts fixed; full prose after the
> ontology discussion.

**Describes:** `skellyforge/skellymodels/standard_human/reference_geometry.py`.
**Salvage:** [`archive/streaming-compatibility-specs/12-standard-human-model.md`](../archive/streaming-compatibility-specs/12-standard-human-model.md).

## What this covers
The **T-pose** each live pose is measured against — one build serves both the orientation solver
(`identity == T-pose`) and the stream schema's rest pose.

## Key facts (committed code)
- Built from composed segments + per-subject measured lengths. Three passes: rest directions (right side
  mirrored via −Y) → origins + rest keypoint positions → per-segment bases.
- **Schematic pose:** ORIGIN branches collapse to the parent's origin (no widths/fan geometry); live
  solves are unaffected (they read live keypoints). Absolute rest *positions* of some points (finger
  origins, degenerate skull points) are schematic, not metric.
- **`SegmentReferenceGeometry`** = `origin`, `basis` (rows [x̂, ŷ, ẑ]), `length`.
- **Rest approximate axis:** an authored `_TWIST_OVERRIDES` entry is **authoritative** where the
  schematic geometry can't be trusted (off-chain / degenerate targets), taking precedence over the
  target-position branch — this is the 2026-08-14 fix that keeps the **head's forward axis anterior**
  (the shared off-chain `nose` slot is last-writer-wins and must not drive the head's frame).
- `nose` is popped from the returned keypoints (off-chain, no single canonical rest position; the tracker
  supplies it live).

## Known, inert
The reference "skull" is partly degenerate (eyes coincide with `head_center` at rest). Inert: the
realtime **skull fit builds its template from measured pair-distances + observed positions, not the
reference** (see [../02-pipeline/segment-length-estimation.md](../02-pipeline/segment-length-estimation.md)).

## Reconciliation notes
Standardize on `basis[exact-axis-name]`, not "basis[0] = long axis" (name-driven now).
