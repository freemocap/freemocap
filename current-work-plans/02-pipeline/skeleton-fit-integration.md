# SkellyForge connected fit integration

## Backend checkpoint: 2026-09-28

The accepted Forge solver is now an optional post-hoc operation. The configuration
field is `skeletonFitEnabled` (Python: `skeleton_fit_enabled`), default false.
`run_posthoc_mocap_task` publishes the normal prepared reconstruction first, then
calls `fit_saved_skeleton` when enabled. Existing real-time calculations and
keypoint/landmark/segment channels are unchanged. ChArUco is not passed to the
human solver. This adapter currently accepts the `standard_human` model only.

The callable lives in
`freemocap/core/recording/result_processing/skeleton_fitting.py`. It can also
fit an already prepared run without rerunning video analysis. Inputs are the
saved prepared keypoints, mapped landmarks, world segment quaternions, segment
origins, model snapshot and person-scale fit. It does not interpolate, filter,
align, estimate scale, or import Forge development scripts. It calls the
installed `skellyforge.core.skeleton.fitting.fit_human` without changing settings.

`ProcessingStage.SKELETON_FIT` depends on reconstruction, scale fit and timing.
It is after biomechanics in stage order so the existing default stopping point
does not silently enable the optional solve. It is not currently used to
recompute biomechanics or reprojections; those still describe the segment result.

## Saved data

A source named `skeleton_fit:<sensor_group>:standard_human`, with kind `solver`,
distinguishes the solve from the measured tracker and original reconstruction.
It carries the actual returned Forge model geometry, input fingerprint, installed
Python/native code hashes, Ceres version, window processing reports and convergence
status. The group is part of the identity to keep independent solves separate.

Its dynamic channels are:

| Channel | Meaning | Coordinates / units |
| --- | --- | --- |
| SEGMENT_ORIGINS | Fitted segment translations | Input world reference, mm |
| ROTATIONS_WORLD | Fitted segment orientations | Unit wxyz, input world reference |
| SEGMENT_LENGTHS | Fitted lengths of the three flexible axial segments | mm; reference geometry remains in the source |
| LINKAGE_DISPLACEMENTS | Native relaxed-linkage displacement state | Parent segment's local XYZ, mm; no global reference-frame ID |

Original channels remain available. No per-frame full-model JSON copies are
written. Geometry/settings are metadata; dynamic numerical state uses the existing
tall Arrow/Parquet rows. Readers must apply the returned reference geometry and
variable axial lengths when drawing segment endpoints. They must not recompute
the fit or substitute today's skeleton defaults.

Publication uses the existing atomic checkpoint machinery under the recording
lock. Unchanged inputs/code reuse the saved checkpoint. Upstream reconstruction
invalidation removes the fitted channels, completion record and solver metadata.
`keep=True` retains the old run and publishes to a new run. Solver failure or
cancellation before publication preserves the existing recording. Cancellation
is cooperative between native windows, not inside an active native solve.

Progress uses SkellyForge logging plus the normal task reporter. A usable result
can contain nonconverged windows; the saved reports preserve that distinction.

## Validation and next boundary

`test_skeleton_fit_checkpoint.py` uses temporary copies of the prepared test and
sample recordings. It runs the real installed solver, compares every persisted
quaternion, translation, flexible length and linkage displacement to the returned
native state, verifies reload/reuse, and checks failure/cancellation preservation.
The normal playback manifest must still load. These are backend/data checks,
not visual acceptance of the new playback layer.

Both prepared recordings passed the real solve and exact state round trip:
222 frames / 220 converged windows, and 1108 frames / 1106 converged windows.
Observed sequence solve wall times were approximately 92 s and 70 s respectively;
input reading, Parquet publication and comparison add time beyond those numbers.
These runs are not a controlled performance benchmark. Failure and cancellation
checks leave the prior Parquet byte-identical. The UI TypeScript check passes.
Pipeline/store/progress regression tests pass, with existing dependency
deprecation and a managed-thread test warning still reported.

Next: add the processing UI toggle and the fitted playback layer. Preserve the
existing segment layer; add independent fitted-stick and fitted-axis controls,
hover identities and synchronized playback. Derive rendering from saved solver
geometry. The existing Forge viewers remain the visual reference. Test both real
recordings in the app before declaring integration complete. CSV/NumPy/glTF/BVH
export remains subsequent work.
