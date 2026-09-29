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

## Processing controls and playback: 2026-09-28

The motion capture setup's **Post Processing** section now has **Fit skeleton**,
off by default. Its value travels in the existing post-hoc request as
`skeletonFitEnabled`; the section summary indicates when enabled. The filter help
also reflects the current order: gap filling, filtering, then person alignment.

Playback's **Viewport settings** has independent **Fitted skeleton** and
**Fitted axes** toggles. Blue sticks and white origins identify the saved fit;
RGB axes use its saved world quaternions. Original keypoints, landmarks, segments
and their controls remain available. Hover labels identify fitted segments and
their endpoint landmarks. The existing pin inspector's original-reconstruction
numerical details are not extended to fitted state in this step.

`playback_manifest` passes the solver source definition through unchanged.
`services/recording/fitted-skeleton.ts` selects channels with the same recording
clock as the existing playback and checks matching frames, reference coordinates,
units and finite state. `FittedSkeletonInstances` renders the saved Forge display
geometry using saved translations and wxyz quaternions; local Z scales by the
saved axial length/reference length. It does not fit, estimate scale, interpolate,
or add linkage displacements a second time. Static geometry is sent to the
viewport worker when the selected result changes, not on every frame. Switching
results clears the fitted layer; old recordings continue working without a fit.

Validation includes both real recording solve/checkpoint round trips, exact
manifest metadata preservation, TypeScript geometry/visibility tests, and the
existing Parquet browser regression suite. The real-recording browser test
`e2e/fitted-playback.spec.ts` exercises the actual app provider, Parquet worker,
viewport worker and renderer, including backward seeking and independent toggles.
It passed against 222-frame test and 1108-frame sample fitted Parquets. It reads
the file set by `FREEMOCAP_FITTED_PLAYBACK_PATH` and skips explicitly if unset.
Use `PLAYWRIGHT_CHANNEL=msedge` to use installed Edge on Windows. Test-generated
fits used temporary copies; canonical prepared recordings were not changed.
The Electron video checks also pass for both direct playback and compatibility
conversion. Their existing fixture is generated with
`.venv/Scripts/python.exe freemocap-ui/e2e/fixtures/create_decoder_fixture.py`;
the test page now separates its command buttons from playback tooltips so normal
clicks reach them. No production video-control behavior was changed.

### Human visual check

Restart the development backend and UI to pick up both halves. For a recording
without fitted channels, enable **Fit skeleton** in its post-hoc setup and process
it. For the 6 FPS test recording, leave Butterworth filtering disabled. Open
**Playback**, expand **Viewport settings**, and compare **Fitted skeleton** against
**Rigid Body Bones**; enable **Fitted axes** independently. Scrub with the videos
and inspect the shoulder/spine behavior. **Reload result** rereads a newly saved
checkpoint. A recording without a fit says so rather than drawing a substitute.

The app-renderer tests cover data playback; human visual acceptance with the
recording's annotated videos remains the next checkpoint. The existing Forge
viewers remain the visual reference. CSV/NumPy/glTF/BVH export remains subsequent
work, with scapula/shoulder-roll and foot-locking improvements still deferred.
