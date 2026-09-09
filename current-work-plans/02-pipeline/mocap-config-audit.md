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

1. **Post-processing controls are not operative.** The UI sends `filterConfig`,
   but `PosthocMocapPipelineConfig` has no corresponding field and currently ignores
   extras. The active task reconstructs/publishes triangulated trajectories without
   consuming these controls. Connect an explicit filtering stage, validate cutoff
   against resolved recording timing, and preserve raw versus filtered data.
2. **Automatic Blender export is not called by the active Mocap pipeline.**
   Its options exist in the schema, but the managed worker finishes after canonical
   publication. The separate Blender endpoint still exists. Integration must account
   for the exporter’s expected recording artifacts before connecting completion.
3. **Live alignment is pending.** Neither the new custom offset nor the posthoc
   body/foot estimator is applied to live output. Add an initial evidence window,
   one frozen reference per session, explicit reset, and consistent camera/entity
   transforms. A recording request carrying these settings configures posthoc work.
4. **Base-camera selection is pending.** The proposed first-calibration-camera
   default and explicit camera choice are not implemented. This pass preserves the
   panel's current calibration/person semantics; it does not silently select a camera.
5. **Calibration selection needs a single resolved source.** The UI displays
   `loadedCalibration`, while the payload can prefer `mocap.calibrationTomlPath`.
   Also, reopening the entire modal still mounts the folder-calibration loader.
   Move selection/loading ownership outside presentation components and derive
   status from the exact calibration selected for processing.
6. **Outer modal Cancel/Save labels do not describe transactional behavior.**
   Most controls write immediately to persisted Redux state; Cancel does not undo
   them. Use Close/Done, or introduce a deliberate draft-and-apply model. The inner
   transform editor does have separate draft/accept/cancel behavior.
7. **Recording QA remains necessary.** Foot-contact thresholds are provisional;
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
