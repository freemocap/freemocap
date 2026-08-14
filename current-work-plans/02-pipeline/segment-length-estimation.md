# Segment-Length Estimation (+ enforcement / rigid fit)

> **Scaffold (2026-08-14) — pending ontology revision + in-flight rework.** This is the doc whose *framing*
> is being reconsidered: the task is **segment-length estimation** (and holding those lengths while
> following the observed pose), **not "skeleton rigidifying."** Name (`skeleton_rigidifier` → ?) and scope
> settle at the ontology check-in. The module is also mid-rework on disk (542-line diff) — author against
> the settled version.

**Describes:** `freemocap/core/tasks/mocap/rigid_body/skeleton_rigidifier.py` (the freemocap wrapper) +
`skellyforge/kinematics/online_segment_lengths.py` (`SegmentLengthEstimator`),
`skellyforge/kinematics/skeleton_rigidifier.py` (`TreeRigidifier`), `rigid_point_set.py` (skull fit).

## What this covers
Per-frame: map tracker keypoints → standard-human names, advance per-segment **length estimators** with
the *measured* (non-extrapolated) keypoints, then a single forward pass that **holds the estimated
lengths while following the observed direction**. ≥3-point segments (the skull) get the rigid-body
template fit; 2-point segments keep the span/edge path. Lengths feed the stream schema.

## Key facts (committed code — verify post-rework)
- Per-group state (body / left hand / right hand); the head additionally gets a `RigidPointTemplate`
  (21 skull pair-distances, rebuilt ~every 30 frames, chirality-stabilized).
- The skull template is built from **measured pair-medians + observed positions**, not the reference
  geometry — which is why the reference skull's degeneracy is inert.
- **S2 (plan):** the old per-frame `StreamingSegmentLengthMonitor` (retired `canonical_body.yaml` model)
  still runs in the aggregator and is redundant with this estimator — slated for removal.

## Reconciliation notes
Reframe away from "rigidify" toward "estimate + hold lengths." Kill the old-model residue (S2).
