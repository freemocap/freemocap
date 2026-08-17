# Posthoc Rebuild

**Describes (target):** the offline path — recorded videos → calibration/mocap → the same segment model +
kinematics as realtime, batch-optimized. This is the **posthoc parity** workstream of the next iteration.

## What this covers

Rebuilding the posthoc pipeline onto the new data model, so realtime and posthoc share one segment model,
one solver, one length estimator (unbounded window for posthoc — never evicted). Realtime runs online
(per-frame, damped); posthoc runs batch over the full recording — same architecture, different presets.

## Current state

The posthoc / calibration path **still imports the old skellyforge architecture** (`skellymodels.managers`,
`skellymodels.models`, `data_models.trajectory_3d`, `post_processing.*`, `kinematics.segment_lengths`).
That coexistence is the seam this workstream closes.

## Workstream (see [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md))

1. Enumerate every old-layer import in the posthoc/calibration path.
2. Re-point each to the new segment model + kinematics (one model, one solver, one length estimator).
3. Delete the old `managers`/`models` layer + the `tracker_info/canonical_*.yaml` files.
4. Note: `VideoNodeOutputTopic` has an unbounded-queue TODO (posthoc aggregation can't yet run
   concurrently with video nodes) — capture it here when the workstream starts.
