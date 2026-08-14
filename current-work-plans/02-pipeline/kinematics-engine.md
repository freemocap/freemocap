# Kinematics Engine

> **Scaffold (2026-08-14).** Rich on current facts; final prose may shift slightly with the ontology pass
> (the twist tiers touch the segment model).

**Describes:** `skellyforge/kinematics/` — `orientation_solver.py`, `coordinate_frame_ops.py`,
`quaternion_math.py`, `critically_damped_orientation.py`, `rigid_point_set.py`.
**Salvage:** [`archive/streaming-compatibility-specs/11-kinematics-fold-in.md`](../archive/streaming-compatibility-specs/11-kinematics-fold-in.md),
[`14-engine-testing-strategy.md`](../archive/streaming-compatibility-specs/14-engine-testing-strategy.md),
[`archive/phase-1-work-plans/05-kinematics-foldin-rotations.md`](../archive/phase-1-work-plans/05-kinematics-foldin-rotations.md).

## What this covers
Declared keypoints → per-segment world + local quaternions, `identity == T-pose`. The math kernel
(verified sound in the 2026-08-14 audit): `R = liveᵀ·ref`, Gram-Schmidt frame build, Kabsch/Umeyama
(det=+1), classical MDS for rigid templates.

## Key facts (committed code)
- **`build_segment_frame(axes, positions, origin_landmark)`** — the ONE frame builder. Name-driven: each
  axis fills its declared basis slot (x/y/z); the exact axis seeds, the approximate is Gram-Schmidt'd,
  the third is the cross product. Collinearity gate degrades a bad approximate to `(None, False)`.
- **`solve_frame_orientations`** — walks segments in hierarchy order; per segment: swing
  (`rotation_between_vectors(ref.basis[exact], live_exact)`), then **two-tier twist** — resolved from the
  live frame, else damped-minimal via `critically_damped_orientation`. Local = `conj(parent)·child` (D1).
- **`rigid_point_set.py`** — MDS template + rotation-only Procrustes fit for ≥3-point rigid bodies (the
  skull); consumed by the segment-length/fitting stage.

## Future work (not current)
The **linkage/chain layer** that would resolve an under-determined segment's twist from its neighbours
(the retired "chain-resolved" tier) — the constraint/solve layer of [the ontology](../ontology.md), seams
only. `compute_live_bone_basis` is the orphaned breadcrumb (do not delete yet).

## Reconciliation notes
Name-driven everywhere (no "basis[0] = long axis"); two tiers, not three.
