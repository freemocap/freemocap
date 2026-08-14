# Posthoc Rebuild

> **Scaffold (2026-08-14) — SPEC / not started.** Gated behind the F5 realtime-loop close. Content is
> carried from the archived spec until this phase begins (after the ontology discussion + F5).

**Describes (target):** the offline path — recorded videos → calibration/mocap → the same segment model +
kinematics as realtime, batch-optimized.
**Salvage:** [`archive/phase-1-work-plans/12-posthoc-rebuild.md`](../archive/phase-1-work-plans/12-posthoc-rebuild.md)
(the REVISIT notes).

## What this covers
Rebuilding the posthoc pipeline onto the new data model, so realtime and posthoc share one segment model,
one solver, one length estimator (unbounded window for posthoc — never evicted).

## Known state / dependencies
- The posthoc / calibration path **still imports the old skellyforge architecture** (`skellymodels.managers`,
  `skellymodels.models`, `data_models.trajectory_3d`, `post_processing.*`, `kinematics.segment_lengths`) —
  the coexistence is expected until this phase.
- Blocked on: the **F5 gate** (realtime closed) and the ontology discussion.
- `VideoNodeOutputTopic` has an unbounded-queue TODO (posthoc aggregation can't yet run concurrently with
  video nodes) — capture here when this phase starts.

## Reconciliation notes
Author fresh from the settled realtime model; do not re-import the retired managers/models layer.
