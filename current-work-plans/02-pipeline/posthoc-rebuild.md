# Posthoc Rebuild

**Describes (target):** the offline path — recorded videos → calibration/mocap → the same segment model +
kinematics as realtime, batch-optimized. **Deferred by decision (2026-08-24)** — documented here so the
breakage is explicit instead of discovered.

## Current state: broken-if-invoked, not merely pending

The old skellyforge system (`skellymodels/`, `post_processing/`, `data_models/`,
`tracker_info/*.yaml`) is **deleted from skellyforge HEAD** — and freemocap pins that exact commit.
Yet the posthoc paths still import it:

- `core/tasks/mocap/mocap_helpers/skeleton_from_mediapipe_observations.py` →
  `skellymodels.managers.human.Human`, `MediapipeModelInfo`/`RTMPoseModelInfo`, the
  filter/interpolation quartet, `data_models.trajectory_3d.Trajectory3d`.
- `core/tasks/mocap/mocap_helpers/charuco_model_from_observations.py` →
  `skellymodels.managers.board.Board`, `CharucoBoard*ModelInfo`, same quartet.

These imports are lazy (hidden inside functions), so the realtime app runs fine — but invoking posthoc
mocap or charuco processing raises `ImportError` against the installed package (which ships only
`core/` + `definitions/`). `posthoc_pipeline_manager.py` notes the modules are "(still-deferred)".

## Workstream (when scheduled — see [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md))

1. ~~Enumerate every old-layer import in the posthoc/calibration path~~ (done — the two files above).
2. Re-point both paths to the new core: load the model via `SkeletonDefinition.from_default_yaml()`,
   solve batch-wise with `hydrate_skeleton(require_all=True)` over the full recording; realtime = damped
   online, posthoc = undamped batch — one model, one solver, different presets. This is also where the
   neutral-naming decision lands (a non-human board wants `SkeletonDefinition` renamed neutral).
3. ~~Delete the old system~~ (already done upstream — nothing left to delete on the skellyforge side).
4. Note: `VideoNodeOutputTopic` has an unbounded-queue TODO (posthoc aggregation can't yet run
   concurrently with video nodes) — capture it here when the workstream starts.

Until then the honest options are "don't invoke posthoc" or making the imports fail loudly at startup;
the lazy imports are the only reason this is latent.
