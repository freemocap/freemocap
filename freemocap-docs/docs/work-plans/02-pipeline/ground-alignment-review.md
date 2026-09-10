---
mdx:
  format: md
plan_status: ongoing
plan_migrated: "2026-09-10"
---

# Ground alignment and ownership review

2026-09-08. Read-only source/history audit; implementation proposal.
Scope: recent camera matching, live/posthoc integration, reconstruction and ground transforms.
This is not a claim that every legacy module in all four repositories has been audited.

## Historical functionality

SkellyForge main contains `Human.put_skeleton_on_ground` in
`skellyforge/skellymodels/managers/human.py`, called from `pipelines/test_pipeline.py`.
It selects the transition with the lowest maximum foot displacement across visible markers,
uses left/right heel and foot-index centers as origin, heel-to-toe direction as forward,
and neck-minus-foot-center as up. It transforms all of that human's aspects.

That implementation assumes one upright human, uses one frame, does not weight confidence,
does not estimate a plane over multiple contacts, and does not transform camera geometry.
Restore the capability using current Forge primitives, not the obsolete Human/Trajectory stack.
The streaming Forge code has ground-dependent biomechanics but no foot-based ground estimator.

## Specific audit findings

- `matching_fitness._conditioned_points` undistorts pixels, then Triangulator undistorts them
  again. Candidate evaluation repeats that work across source pairs. Share prepared rays and
  normalized coordinates through the numerical evaluation rather than duplicating geometry.
- Evidence graph connectivity is implemented in both `PairAssignmentCosts` and
  `matching_evaluation._supported_edges`. One graph validator/result should serve both.
- Live and posthoc independently select the first 64 names and reject multiple root bounding
  boxes. This is duplicate policy, and root box count does not prove consistent subject identity.
  One detector-aware evidence selector should own this; do not claim multi-person association.
- Matching numerical models, configuration, execution policy and result models share one file.
  Separate domain math types from pipeline continuation policy when moving ownership.
- Live/posthoc `_to_blender` duplicate a conversion already represented by Forge's
  CoordinateSystemTransform. Use the existing convention definition and batch-capable transform.
- `compare_calibrations.py` has another DLT implementation. The shared Triangulator should
  not claim uniqueness until this is consolidated.
- `groundplane_alignment.apply_groundplane_to_cameras` constructs CameraModel without its
  required index and leaves world pose fields at defaults. It is referenced by the pyceres path.
  Fix and test this before using it for foot alignment; do not copy it as another helper.
- The mocap task discards returned per-camera weights. Those weights alone are not detection
  confidence; plain DLT assigns uniform weights. Ground estimation needs actual track validity,
  temporal coverage and reconstruction quality, not invented confidence from solver weights.
- Image references now explicitly preserve source-to-calibration ID association. Retain this;
  transforming camera geometry must preserve both identities, never rename models to source IDs.

## Ownership decisions proposed

| Responsibility | Owner |
|---|---|
| Foot contact evidence, robust plane fitting, rigid transform and diagnostics | SkellyForge |
| Pure DLT/rigid geometry and numerical assignment search | SkellyForge |
| Observation point extraction, detector validity and instance semantics | SkellyTracker |
| Media, capture identity, image geometry and camera intrinsics/extrinsics/projection | SkellyCam |
| Calibration task using board detections and camera geometry | FreeMoCap orchestration |
| Matching execution combining observations, camera models and numerical fitting | FreeMoCap orchestration |
| Live jobs, retries, recording-stage continuation, UI/API and result publication | FreeMoCap integration using existing worker infrastructure |

Camera models/projection currently live in FreeMoCap. Moving only the scorer would strand it
behind those imports. Migrate that cohesive camera primitive layer separately; do not create a
parallel model in a subrepo or add OpenCV to Forge merely to disguise the dependency problem.
Forge ground alignment needs only existing NumPy, Transform, Point and RotationQuaternion.

## Foot-ground estimation in SkellyForge

Proposed module: `skellyforge/core/biomechanics/ground_alignment.py`.
Typed request: named 3D foot contact trajectories, corresponding quality values, timestamps,
contact landmark definitions and body-up evidence. Inputs are in one declared frame and length
unit. The estimator must not import camera, tracker, recording, GUI or FreeMoCap classes.
Return the existing Forge Transform plus support/fit diagnostics, or an explicit insufficient/
ambiguous result. It must not mutate trajectories or fabricate a floor when evidence is absent.

1. Compute point speed from adjacent finite samples and actual positive delta-time:
   speed(t,k) = norm(p(t,k)-p(t-1,k)) / (time(t)-time(t-1)).
   Do not bridge missing samples or long time gaps. Require a sustained dwell interval,
   not a single low-displacement transition. Velocity magnitude is rotation-invariant,
   so camera-zero coordinates need no guessed vertical axis before contact selection.
2. Select high-quality low-speed heel/toe/contact candidates. Keep separate contact episodes,
   cap samples per episode and balance support across feet. Thousands of duplicate stationary
   points must not overwhelm a smaller but geometrically informative contact episode.
3. Generate bounded, deterministic non-collinear triplet plane hypotheses. Score candidate
   support by point-to-plane distance, quality and episode coverage; moving/outlier feet do
   not become inliers simply because they are the lowest samples on an arbitrary Z axis.
4. Refit supported points using weighted PCA:
   c = sum(w*p)/sum(w); C = sum(w*(p-c)*(p-c)^T)/sum(w).
   Plane normal n is the eigenvector of C's smallest eigenvalue, with d = -n dot c.
   Reweight residuals robustly and repeat a bounded number of times. Require adequate 2D
   spatial spread (second eigenvalue), low residual and distinct support episodes/contacts.
   Collinear or competing similarly supported planes yield an unresolved result.
5. Orient n toward body-up evidence, e.g. torso above support, without using the torso as
   the fitted plane normal. A still lifted foot is not automatically a floor contact.
   Sitting, lying, stairs, ramps and feet on different surfaces can remain ambiguous.
6. Construct one right-handed ground frame. Plane fitting determines tilt/height, not yaw.
   Proposed yaw: stable bilateral heel-to-toe direction projected into the fitted plane,
   consistent with the historical behavior; explicitly report if heading is unavailable.
   Origin: supported foot center projected onto the plane. No arbitrary scale adjustment.

Heel/toe detector landmarks are not exact sole contact points. With no sole-offset model,
this is an estimated foot-support plane, not a measurement of the physical floor surface.
Initial thresholds should be expressed in seconds, length/second and length residuals, and
validated against the actual recording; do not hardcode frame displacement or assume 30 FPS.

## Applying the transform consistently

### Configuration and calibration boundary

Expose a typed Mocap configuration, shared by realtime and posthoc, with an
"Automatically align from body" toggle (proposed default: enabled), analogous to camera matching.
This belongs to Mocap settings, not calibration settings. Estimation remains in SkellyForge.

Calibration ground alignment changes camera extrinsics before saving the TOML. Loading that
artifact loads its existing coordinate frame; disabling Mocap alignment must NOT undo it.
The fallback is always the supplied calibration frame, which is not necessarily camera zero.
No "ignore calibration ground plane" switch is part of this feature.

Decision order:

1. Explicit ground-aligned calibration: retain its frame without automatic body alignment.
2. Mocap automatic alignment disabled: retain supplied geometry unchanged.
3. Adequate foot evidence: estimate the foot-support plane and body heading.
4. Feet unavailable/unreliable: estimate a body reference frame from reliable upper-body evidence.
5. Insufficient body evidence: retain supplied geometry and report alignment unavailable.

Body-only alignment is an approximate reference frame, NOT a measured floor. Face and head
landmarks are primary evidence alongside torso landmarks, not a last-resort supplement.
Use available named bilateral eye/ear landmarks for lateral direction and appropriately defined
upper/lower facial landmarks for facial vertical; orthogonalize the axes and determine forward
using the declared landmark convention and nose evidence where available. Do not require a dense
face mesh or assume every detector supplies the same landmarks. Landmark definitions and existing
Forge model semantics determine which constructions are supported.

Build candidate head and torso orientations over a stable time window. Weight evidence by
reconstruction quality, visibility, spatial conditioning and temporal stability, not a fixed
preference for hips/shoulders. Balance anatomical regions so many correlated facial landmarks
do not win merely by count. Head direction and torso direction can legitimately differ: a head
turn or tilt must not be treated as noise or proof of gravity. Use consistent reliable evidence
to choose an approximate reference, and report disagreements/uncertainty rather than forcing
incompatible axes together. Require nondegenerate axes and reliable left/right labels; do not
average different subjects. A head-only reconstruction must be supported when its geometry is
sufficient, with a stable facial/head center as origin. When other regions are available, select
and report a reliable anatomical anchor without requiring a pelvis or automatically preferring it.
Do not invent floor height or leg length. A seated person can therefore be centered and
approximately upright without claiming their invisible feet lie on Z=0.

Report typed outcomes distinguishing explicit ground, estimated foot support, estimated body
reference and unchanged calibration frame. Freeze a chosen alignment for the recording/live
session; no per-frame recentering or automatic jump from body to feet when feet later appear.
All modes transform camera geometry and all reconstructed entities together.

Implementation check: verify groundplane_applied/groundplane_aligned consistency in the active
Anipose calibration task, artifact writing and loading. PyCeres is dormant and outside this
implementation scope; its audit findings are deferred, not prerequisites for this feature.

Only use the foot fallback if no explicit ground reference was supplied. A known board-defined
floor takes precedence. Posthoc estimates one transform and freezes it for the whole recording;
live estimates from an initial stable window and freezes it, with an explicit reset rather than
continuous rotation chasing the person's feet.

For old-to-ground transform X' = Q X + b, and camera x = R X + t:

    R' = R Q^T
    t' = t - R Q^T b

Then R' X' + t' = R X + t: reprojections must remain invariant. Apply the SAME transform to
all reconstructed subjects/boards and camera poses. Preserve camera IDs, indexes, intrinsics
and matching associations. Orientations transform by Q; displacement vectors rotate without
translation. Prefer alignment before pose fitting and ground-dependent biomechanical measures,
so we do not independently patch derived outputs afterwards. Raw 2D observations remain unchanged.
Do not overwrite the supplied calibration artifact; record the alignment with result geometry.

## Work order and checks

1. Agree on foot-support plane and heading semantics; implement/test the pure Forge estimator.
2. Ensure camera-transform preservation in the active integration and consolidate duplicated
   convention conversion. Do not revive or refactor the dormant PyCeres path for this work.
3. User commits/pushes Forge and updates the Git dependency; never install its checkout editable.
4. Integrate the posthoc fallback, retain reconstruction quality, apply one transform to all geometry.
5. Test tilted/translated synthetic tracks, irregular timestamps, missing/noisy contacts, moving
   feet, collinear support and ambiguous surfaces. Include head-only data, occluded hips/feet,
   head turns/tilts, conflicting head/torso orientations and uneven landmark counts across regions.
   Verify rigid distances and camera reprojection
   invariance, and that explicit ground alignment is never applied a second time.
6. Real recording QA, then live frozen alignment. Resume broader numerical ownership migration
   in bounded changes, with source/repo integration checks between them.

## Implementation checkpoint

Implemented the first numerical chunk in SkellyForge:

- `core/biomechanics/body_alignment.py`: typed anatomical reference tracks, configuration,
  quality/time-weighted rotation estimation, stable-interval selection and explicit unresolved
  result. Head-only tracks are supported; no anatomical region wins by landmark/frame count.
- `core/biomechanics/ground_alignment.py`: typed contact tracks, dwell/speed filtering,
  landmark-balanced episode representatives, bounded deterministic plane hypotheses and weighted
  PCA refinement. Returns one existing Transform or an explicit unsupported/ambiguous result.
- Ten focused tests cover head-only alignment, sampling density, irregular timestamps, missing
  evidence, head motion, invalid rotations, tilted support, collinearity, elevated outliers,
  moving feet, rigid distances and algebraic camera reprojection invariance. The full Forge test
  suite also passes (one skipped test).

These are numerical building blocks, not an app-ready feature. No FreeMoCap runtime imports or
dependency sources were changed. The user commits/pushes Forge and updates the Git dependency
before integration tests can use it in FreeMoCap.

Remaining: derive quality-bearing body-frame tracks from existing model/pose semantics (including
face/head and authored rest orientation), implement the single configurable Mocap selection policy,
apply/persist one whole-scene transform, and expose the shared UI/API setting. Validate the active
Anipose alignment flag and perform actual camera-model reprojection tests during integration.
The first plane solver uses episode representatives and one PCA refinement; iterative robust
refinement and competing-plane diagnostics remain to be evaluated with noisy recording evidence.
Do not describe it as physical-floor detection or as already wired into either Mocap mode.

Second Forge checkpoint: `BodyReferenceTrack.from_segment_poses` now composes measured pose
orientation with inverse authored rest orientation and excludes missing/direction-only/carried-roll
poses. A test hydrates the actual default human after a known scene rotation and verifies recovery
across rigid-fit segments. `reference_alignment.py` owns the shared enabled/explicit-ground/
feet/body/unchanged selection policy, returning the existing Transform and typed diagnostics.
Fifteen focused tests pass. The active Anipose path sets groundplane_aligned; PyCeres remains deferred.
FreeMoCap's installed dependency was verified to contain the first estimator checkpoint.
The second checkpoint needs the normal user commit/push/dependency update before app integration.
Remaining adapter work is observation-quality propagation and model-declared selection of alignment
regions/contact landmarks; the pose-to-body-axis conversion itself is implemented in Forge.

Third checkpoint: Forge now declares alignment regions and foot-contact landmarks in
`definitions/human_skeleton/alignment_definition.yaml`, resolved to existing model objects by
`core/biomechanics/alignment_definition.py`. This keeps anatomical name rules out of FreeMoCap.
Seventeen focused Forge tests pass. FreeMoCap now uses Forge's authored coordinate conventions
in both live/posthoc conversion (batched in the live path), and CameraModel.in_world_frame applies
an existing Forge Transform while preserving identity/intrinsics and recomputing world poses.
Eleven FreeMoCap geometry/reconstruction/matching tests pass. These camera transforms are tested
building blocks; automatic alignment and UI settings are not wired yet. The new Forge definition
needs the normal commit/push/dependency update. Observation-quality propagation, evidence collection,
result persistence and live/posthoc control wiring remain.

Evidence checkpoint: SkellyTracker TrackerMapping/CompositeTrackerMapping now expose
apply_with_quality, returning MappedLandmarkEvidence. Position calculation uses the existing
mapping; quality takes the weakest required source, including anatomical-offset frame/origin/
length dependencies. Missing measurements remain absent; invalid or mismatched quality fails.
This is a conservative evidence score, not a calibrated probability or an anatomical accuracy claim.
Nineteen mapping tests pass. The user must commit/push SkellyTracker and update FreeMoCap's Git
dependency before the pipeline consumes this method.

Posthoc triangulation now returns RecordingTriangulation with explicit source/name axes and the
existing TriangulationResult, retaining camera contributions and reprojection errors. It does not
copy the solver model or call those weights detection confidence. Nine affected FreeMoCap tests
pass, including exact-error/source-order checks on the renamed-video fixture. Automatic alignment
and UI controls are still pending; no app-testing request yet.

Collector checkpoint: installed Tracker/Forge updates verified. FreeMoCap's
`core/reconstruction/alignment_evidence.py` now integrates quality-bearing tracker mapping with
Forge's declared anatomical regions and contact landmarks. It hydrates only selected regions,
builds rest-corrected BodyReferenceTracks and measured FootContactTracks, and retains missing
orientations as missing samples. Thirteen affected reconstruction/evidence tests pass, including
the shipped human model with head-only input and low-quality rejection. The collector accepts
explicit timestamps and measured 3D quality; it does not infer confidence from solver weights.
No dependency update is needed for this checkpoint. Remaining work: compute reconstruction-quality
scores from observation/reprojection evidence, connect shared recording timing, invoke the policy,
persist/apply the scene transform, wire UI/API settings, and add live collection/reset lifecycle.

## Posthoc app checkpoint

Posthoc is wired through bodyAlignment in the API and "Automatically align from body" in
Mocap triangulation settings (enabled by default). It estimates before model reconstruction,
applies one transform to all triangulated points and camera geometry, and stores the additional
transform/outcome/anchor in the Parquet spatial-reference descriptor, not recording_info.json.
Explicit ground calibration, disabled alignment and insufficient evidence preserve input geometry;
single-camera planar data supplies no automatic alignment evidence. The calibration TOML is unchanged.

RecordingGroupTiming now serves both processing and publication via SkellyCam timing resolution;
absent timestamps still use frame numbers/FPS. Geometric quality currently requires two positive-depth
views with low pixel reprojection error, using 1/(1+(error/5px)^2), then the mapping's weakest-source
rule. It is NOT calibrated detector confidence. Detector confidence was already used to admit
observations; cross-detector confidence calibration and ray-conditioning gates remain refinement work.
The distance/speed thresholds are provisional and need recording QA.

Backend tests cover transform/projection invariance, explicit/disabled preservation, bad geometry,
head-only evidence, API configuration serialization, publication and reprocessing. TypeScript checks
pass. First app QA: restart backend normally, process an unaligned-calibration recording with the
toggle on/off, then verify a board-ground-aligned recording stays unchanged. Check both cameras and
skeleton in saved playback. Head-only data should center on the head, not invent a physical floor.
Realtime collection/freezing/reset and its UI control are NOT wired yet; verify posthoc before that
next integration step. This checkpoint requires no subrepo dependency update.

## Reference-frame controls: return to processing integration

The Mocap setup order is Process directory, Detectors, Calibration & triangulation,
Post-processing, Exports. The geometry group keeps camera calibration selection,
triangulation/matching, and output reference-frame controls as distinct subsections.
Exports contains the existing Blender controls; this reorganization does not add exports.

Current implementation: automatic body alignment is connected to processing. The custom
transform editor remains local UI state and does not affect a processing request.

Next implementation contract:
- Resolve the base frame from the supplied calibration, a selected calibration camera,
  or body evidence. Preserve an explicitly ground-aligned calibration by default;
  otherwise use the first camera geometry in calibration order, not video ordering.
- Persist one canonical custom rigid transform in the Mocap configuration. The various
  displayed formalisms and mm/m units are views of that transform.
- Custom replacement uses T=C from the original calibration coordinates. Custom adjustment
  uses T=C B, where B is the selected base transform (column-vector convention).
- Apply the resolved transform consistently to all reconstructed entities and cameras.
  Reuse SkellyForge's transform mathematics and the existing camera-model conversion.
- Keep calibration solving a separate task. Never rewrite the supplied calibration TOML.
- Offer explicit export of resolved camera geometry to a new calibration TOML. Body-based
  export requires successfully resolved evidence. Preserve truthful ground-plane metadata.
- Verify selected-camera, body, replacement and adjustment modes through the API before
  claiming the custom editor is available for actual processing.

### Confirmed reference-frame ordering

Base selection and custom adjustment are separate stages. Default base selection should
preserve ground-plane calibration when declared in the loaded geometry; otherwise select
the first calibration camera. Body alignment and explicit camera selection are base choices.
The custom transform is always an additional offset after that base, T = C B. Do not present
custom replacement as a competing base mode.

Current UI separates these stages and exposes the existing calibration/body behavior.
Individual-camera selection and application of the custom offset still require API and
processing implementation; do not claim these choices are operative until wired and tested.
