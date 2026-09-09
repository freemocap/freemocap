# Mocap configuration audit — 2026-09-09

The panel has a reasonable component structure: shared section/row controls, one
Redux configuration, and one matrix shared by the transform representations. It
does not need a wholesale rewrite. Several behavior and integration gaps matter
more than cosmetic cleanup.

## Corrected in this pass

- `freemocap-ui/src/components/common/settings-layout/settings-section.tsx`
  keeps collapsed content mounted. Reopening a section preserves its draft state
  and does not rerun `RecordingCalibrationOptions`' calibration-loading effect.
- `freemocap-ui/src/components/mocap-setup/transform-editor.css` consolidates
  repeated formalism-card rules without changing their effective appearance.
- `mocap-triangulation-settings.tsx` describes the actual subset-weighting solver
  and its normalized-coordinate error target. The target is not measured in pixels.
- The shared request builder in
  `freemocap-ui/src/store/slices/mocap/mocap-thunks.ts` sends the enabled custom
  offset in start-recording, stop-recording, and process-recording requests.

## Connected posthoc contract

The JSON field is `mocapTaskConfig.bodyAlignment.additional_transform`:

```json
{"matrix": [1, 0, 0, 125, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}
```

`null` means no custom offset. The matrix is row-major, with column-vector action
`p' = R p + t`. Translation is in millimeters; axes are reconstruction coordinates
(X right, Y forward, Z up). This example translates output 125 mm along X.

`freemocap/core/reconstruction/reference_transform.py` validates finite values,
16 entries, the homogeneous bottom row, orthonormality, and determinant +1.
`MocapAlignmentConfig` carries the validated offset through the existing API and
worker configuration. No separate endpoint or duplicated request builder is needed.

`mocap_alignment.py` composes `T = C B`: custom offset C after the existing base
alignment B. Saved ground takes precedence over automatic person alignment;
disabled alignment or insufficient evidence retains the calibration base. Custom
offsets still apply in those cases. All triangulated entities and camera geometry
receive the same composite transform before skeleton reconstruction and publication.
Single-camera pixel-space reconstruction rejects millimeter offsets explicitly.

`SpatialReference` stores the base alignment diagnostics and custom offset
separately. This preserves the distinction between estimated foot support, body
reference, supplied ground, and a user's arbitrary offset. Published points are
already transformed; playback/reconstruction must not apply the metadata again.
The supplied calibration TOML is not rewritten.

The active Anipose writer sets `groundplane_aligned` from the successful ground
solve. Calibration save/load maps that flag to/from `metadata.groundplane_applied`,
which is the flag displayed by the panel.

## Remaining findings and next work

1. **Automatic Blender export is not called by the active Mocap pipeline.**
   Its options exist in the schema, but the managed worker finishes after canonical
   publication. The separate Blender endpoint still exists. Integration must account
   for the exporter’s expected recording artifacts before connecting completion.
2. **Live body/foot alignment is deferred.** Manual streaming reference offsets
   are connected through the calibration controller (see checkpoint below).
   Automatic body/foot estimation is not part of the current streaming work.
3. **Base-camera selection is pending.** The proposed first-calibration-camera
   default and explicit camera choice are not implemented. This pass preserves the
   panel's current calibration/person semantics; it does not silently select a camera.
4. **Calibration selection needs a single resolved source.** The UI displays
   `loadedCalibration`, while the payload can prefer `mocap.calibrationTomlPath`.
   Also, reopening the entire modal still mounts the folder-calibration loader.
   Move selection/loading ownership outside presentation components and derive
   status from the exact calibration selected for processing.
5. **Outer modal Cancel/Save labels do not describe transactional behavior.**
   Most controls write immediately to persisted Redux state; Cancel does not undo
   them. Use Close/Done, or introduce a deliberate draft-and-apply model. The inner
   transform editor does have separate draft/accept/cancel behavior.
6. **Recording QA remains necessary.** Foot-contact thresholds are provisional;
   estimated support is not a guarantee of the physical floor. Check unaligned,
   board-grounded, seated/head-only, and noisy-contact recordings, including saved
   playback with custom rotations/translations. Resolved-camera TOML export remains
   a separate feature and must preserve truthful ground metadata.

## Verification

- 23 backend tests: alignment, custom/base composition, camera projection and
  identity preservation, invalid matrices, metric/pixel rejection, schema roundtrip,
  evidence quality, and existing recording publication regressions.
- 7 Playwright tests: transform representations, unit conversion, invalid edits,
  acceptance/cancel, mounted collapse state, and actual outgoing payloads for all
  three recording/processing actions with the custom offset enabled and disabled.
- TypeScript compilation. No full recording or live-camera QA in this pass.

## Filtering checkpoint

`mocapTaskConfig.filterConfig` now accepts `enabled`, `method: "butter_low_pass"`,
`cutoff` in Hz, and integer `order` (1–10). Defaults are enabled, 6 Hz, order 4.
The panel has an explicit off switch and derives timing from the recording;
there is no manually entered sampling rate. Invalid settings fail validation.

`freemocap/core/reconstruction/posthoc_filtering.py` applies forward/backward
Butterworth filtering after reference alignment and before global scale fitting
and reconstruction. It uses median timestamp spacing to resolve the nominal rate
and rejects cutoff at or above Nyquist, including floating-point boundary noise.
Each measured run is resampled within its time support, filtered on a uniform
grid, and evaluated at the original measured timestamps. Missing observations and
time gaps greater than 1.5 nominal intervals separate runs. A run of at most
`3 * (order + 1)` observations remains unchanged and is counted in the report.
No missing sample is filled or admitted as scale-fitting evidence.

Publication stores aligned, unfiltered triangulation as `RAW_KEYPOINTS_3D` and
the exact reconstruction input as `KEYPOINTS_3D`, including when filtering is off.
The reconstruction source explicitly declares its `point_kind`. Saved reconstruction
requires the matching raw/filtered selection and checks the frozen fit against
those exact values; it does not apply filtering again. The filtered channel and
report are removed when their stage is invalidated, while raw data survives.
Filter checkpoints include configuration, timing-bearing input/output signatures,
and the report; even unchanged short-run output cannot hide a settings change.

The run's `processing.mocap.filtering` report retains the algorithm version,
configuration, resolved sampling rate, filtered-run count and preserved-short-run
count. Publication rejects filtered streams that change point names or missingness.
Progress now distinguishes filtering and skeleton reconstruction.

Saved-reconstruction source descriptors require `point_kind`; regenerate processing
results before using the saved-reconstruction API with descriptors lacking it.

Validation: 84 backend tests pass across filtering, store invalidation, raw/filtered
Parquet preservation, frozen-fit reload, reference alignment and managed pipelines
using generated videos. The request test verifies enabled/disabled filtering options
on all three start/stop/process actions. TypeScript compilation passes. Real-camera
recording QA and long-recording performance checks remain.

## Streaming calibration reference frame

The Capture volume controller in the streaming sidebar exposes **Reference frame…**
and **Reset frame**, reusing the transform editor. Accepted matrices travel through
the existing live pipeline config API as `aggregator_config.reference_transform`.
The controller explicitly selects its displayed calibration path when applying.
Edits immediately update the viewport through its reference-transform message
channel, independently of calibration availability or a processing API response.
Loaded camera geometry uses the transform and a separate axes helper shows its
inverse. The on-demand renderer invalidates when the transform changes.
Offline edits also configure the next pipeline start; connected edits apply live.
Buttons use the shared secondary style and color, border, and shadow tokens.

`CalibrationStateTracker` retains source geometry separately from transformed
geometry. Each edit replaces the absolute offset from the source; reset restores
the source frame, and calibration reloads apply the configured offset once.
Transforms use reconstruction axes and millimeters, converted to the camera
extrinsics convention before rebuilding geometry and the triangulator. Camera
identities and projections are preserved. Reference edits reset the temporal
filter, point gate, and skeleton state. Pixel-space single-camera output is withheld
while a metric reference offset is active.

The source TOML is unchanged. Arbitrarily transformed in-memory geometry does not
claim a ground-plane alignment. Streaming and posthoc offsets remain independent.
Automatic foot alignment and the other previously identified broken features are
deferred per the user's current scope.

Validation: 26 backend calibration/alignment tests, a browser test exercising
editor acceptance/cancel/reset, live request payloads, rendered camera and inverse
axes positions through the production forwarding hook, including a delayed API
response, and TypeScript compilation.
Actual live-camera QA remains.

## Calibration selection consistency checkpoint

Reference-frame controls are commented out in the streaming and mocap settings
panels; their implementation is deferred.

The displayed `calibration.loadedCalibration` owns calibration selection for
start-recording, stop-recording, processing, and live API requests. The separate
mocap path override is removed. Requests reject an in-progress calibration load.
Successful selection changes and clearing propagate to connected streaming.

Opening recording options only discovers available files; choosing a recording
or most-recent file is explicit. Automatic startup discovery cannot overwrite a
selection, pending load, dismissed selection, or failed load. Late load responses
are ignored; failed or missing recording calibrations clear displayed geometry.
Playback camera geometry comes from its recording bundle, independently of the
calibration selected for streaming or another processing request.

Backend null selection no longer picks a recording-local or most-recent file.
Multicamera posthoc processing requires an explicit TOML; single-camera planar
processing remains available. Clearing live selection invalidates its geometry.
Unreadable selected files raise errors and invalidate geometry instead of retaining
another calibration. Source changes reset temporal reconstruction state.

Validation: 14 backend calibration tests, 4 browser regression tests (request
payloads, selection changes, clearing, load races, options remounting, and viewport
transforms), and TypeScript compilation passed. Hardware recording is being tested
by the user; this pass does not start cameras or recording.
