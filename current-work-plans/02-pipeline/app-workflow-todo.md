# Recording to processing to playback: app integration TODO

Planning estimate and recommended implementation order, 2026-09-05.
Companion contracts: [posthoc rebuild](posthoc-rebuild.md) and
[processing and playback](processing-and-playback-integration.md).

## Where we are

Code review entry point: `freemocap/core/recording/recording_guide.md`. Recording code uses
`data_descriptors`, `sample_encoding`, `parquet_storage` and `result_processing` packages,
with `playback_queries.py` directly under recording. Concrete two-word module names distinguish
checkpoint publication from reconstruction completion. The Parquet contract is unchanged.
Next: review descriptors and sample columns with the user before extending the data contract.

### Output scope — 2026-09-06

The user reports a clean processing run. Pause additional export development for a data-model
discussion. A recording represents a capture volume, with potentially multiple humans, animals,
objects and calibration boards; it is not a single tracked person's model container.

The only numerical data output currently enabled by posthoc mocap is the canonical Parquet,
including its self-describing model/measurement data. No provisional `output_data` NPY/CSV files,
top-level `tracker_schema.json`, or model/measurement JSON mirror are written. Recording metadata
JSON is reserved for capture-level information and is left untouched by numerical publication.
Automatic Blender export is disconnected from this processing task. Calibration retains its TOML
artifact; observation JSON, reconstructed-board NPY and realtime Charuco disk-cache production are
disabled. A future output layout must be agreed before rebuilding exports piece by piece.

### Real-world test handoff — 2026-09-05

2026-09-06 acceptance blocker: `freemocap_test_data` contained an incompatible saved scale-fit
descriptor missing `inputs`. Publication and playback rejected that output. Mocap now validates
existing metadata before creating workers; playback reports a file-specific 422 error. Eight
focused tests pass, including rejection before worker creation and preservation of invalid input.
The affected Parquet and JSON mirror were hash-verified into
`C:/Users/jonma/freemocap_data/recovery_backups/freemocap_test_data_2026-09-06_metadata`
and removed from the recording folder; original videos and calibration remain in place.
Next acceptance action: restart the app/backend and process `freemocap_test_data` again.

The basic fresh-recording workflow is ready for user acceptance testing. Current preflight:
60 Python recording/storage/playback/calibration/decoder tests, six TypeScript playback tests,
frontend type checking and changed Python file lint checks pass. This is automated readiness;
the complete workflow has not yet passed visual acceptance in the running app.

Completed-job playback navigation preserves the recording's parent directory. Playback prefers
original synchronized videos. The video controller supplies the exact presented recording
timestamp to the numeric player, and each camera resolves its own native frame at that time.

User run-through:

1. Restart the backend and UI so both load the current code.
2. Make a fresh 10–20 second multicamera recording with visible movement and brief pauses.
3. Open mocap processing. Verify the selected folder and calibration. Check automatic local
   calibration loading when present, or select the most recent appropriate calibration. If a
   calibration must be computed, complete the separate calibration task before starting mocap.
4. Process the recording, then open playback from the completed job. Confirm the correct folder,
   original videos and reconstructed 3D appear.
5. Play, pause, step forward/backward, scrub near the end, return near the start and revisit frames.
   Confirm camera images and 3D remain aligned. An uncached backward request may take time because
   decoding proceeds incrementally from the beginning; revisited cached frames should be faster.
6. Restart the app and reopen the same recording. Its saved result should load without rerunning
   detection. Record the first failing action, recording directory and backend/UI error if it fails.

Advanced stage reprocessing controls and the `.freemocap.mp4` export remain subsequent milestones.

Capture has user-confirmed camera operation. Posthoc has shared numerical reconstruction,
canonical publication, saved-input reload, fit-input validation and numerical completion records.
The focused suite has 91 passing tests. This does not establish real-app end-to-end acceptance.
The user has now confirmed that posthoc processing completes in the app. Cosmetic QA is deferred.

Startup regression: the camera-only WebSocket consumer now passes group-local frame cursors to
SkellyCam. Six focused WebSocket/relay tests pass, including empty-manager startup and independent
group counters. A fresh camera-preview check in the running app remains required.

The existing `/mocap` API and application pipeline manager launch processing. `/posthoc` provides
cancellation. Canonical `/playback/{recording_id}/manifest` and `/window` routes now supply saved
model definitions and bounded numeric arrays to `RecordingPlaybackProvider.tsx`. The provider
supports result/group selection, missing samples, reload, stale-response cancellation and data-only
play/seek controls. The old viewport Parquet decoder is removed. Media bundle caches include the
recording's parent directory. Numeric requests identify the exact committed file revision.

Validation for this chunk: 44 focused Python tests and two TypeScript adapter tests pass; frontend
type checking passes. Tests include actual HTTP routes, 30/120 Hz groups, null samples and atomic
overwrite with an open Windows playback snapshot. These do not establish visual app acceptance.
The local `freemocap_test_data` descriptor inspected during validation lacks required fit-input
evidence. The completed recording path was requested from the user for real-output playback testing.

Media-backed 3D playback uses the exact recording timestamp of the presented leader frame,
then samples the selected group's data by recording time through its saved timeline.
Camera timestamps remain SkellyCam's recorded or inferred values. The main controller steps the
leader video's native timeline and resolves each follower's frame independently at recording time.
SkellyCam sequentially decodes every intervening frame; backward seeks reopen and decode from the
beginning. Posthoc VideoHelper uses that same decoder. Browser playback draws decoded images to
canvases as a complete camera set, with no direct browser time seeks. Unprocessed recordings use
SkellyCam timing through the media endpoint without requiring a reconstruction. The encoded grid
and advanced reprocessing UI remain incomplete.

Sequential playback is correctness-first: backward seeks can be slow and playback slows down if
the complete camera set cannot decode at the requested speed. The decoder pool holds eight open
readers and a shared 256 MiB LRU cache of requested JPEG frames, keyed by file identity and frame
number. Cache hits avoid decoding/encoding and never move a decoder's position; they remain usable
even after decoder eviction. Oversized images are returned without entering the cache. The byte
budget covers cached JPEG payloads, not decoder buffers. Cache misses still decode intervening
frames. Visual app acceptance remains pending.

Validation for sequential playback/calibration: 19 Python tests and three TypeScript timing tests
pass, along with frontend type checking. Coverage includes actual frame HTTP responses, backward
posthoc reads after cache eviction, captured/inferred timing, and read-only unprocessed-media
inspection. Local sibling packages are installed editable in the FreeMoCap environment; use
`uv run --no-sync freemocap` for this uncommitted development state so pinned Git dependencies do
not replace those checkouts. The SkellyCam decoder requires PyAV 18.1 or later for display rotation.

Calibration: mocap resolves an explicit TOML first, then the recording-local artifact, then the
last-successful artifact when multiview triangulation needs geometry. Ambiguous local files require
explicit selection. The mocap panel auto-loads the local calibration and exposes Use most recent
calibration and Calibrate videos in selected folder. The latter dispatches the existing separate
calibration task; it never starts calibration inside mocap. Missing calibration is not an error for
single-camera planar processing. Calibration load responses are guarded against obsolete requests.

Timing-binding validation: nine focused Python tests, two TypeScript timing tests, Ruff and frontend
type checking pass. Coverage includes recorded camera offsets, imported-video inferred timestamps,
nonzero frame ranges, reordered media bindings, mixed 30/120 Hz sampling and missing/ambiguous
bindings. Real-app visual playback has not been validated. Newly published camera descriptors
require `video_filename`; existing outputs without it need republishing before canonical media
playback. Unbound annotated/derived videos fail explicitly; exports must publish their own mappings.

## Milestone A: first usable workflow in the real app

### Focused audit, 2026-09-05

The reviewed reconstruction path uses SkellyForge hydration, scale fitting, roll resolution and
biomechanics through the shared per-frame reconstruction function. Mapping remains in SkellyTracker.
Recording descriptors and renderer adapters belong in FreeMoCap because they bind these outputs.
This is a focused audit, not full application acceptance.

Fixed two integrity issues: observation overwrite strictly validates the complete descriptor instead
of silently discarding incompatible fit records from retained runs; playback resolves XYZ/WXYZ and
bone ordering from channel declarations and rejects ambiguous reference-frame selection.
An incompatible existing recording therefore fails validation without alteration; this does not
provide a migration path for recordings missing required fit-input evidence.
Validation: 34 focused Python tests, three TypeScript adapter tests, and frontend type checking pass.

Before expanding exports or advanced restart UI:

- Explicit video/group/time associations are connected to the 3D provider and sequential video
  controller. Validate actual app seeking, mixed-rate follower selection, and decoder throughput.
- Generate playback API types through the existing contract path; the handwritten channel types
  and static-scalar assumptions still need alignment with declared components and units.
- Remove unnecessary playback dependence on full streaming message composition by sharing only
  the model-definition projection. Consolidate repeated recording-channel array decoding.
- Consolidate live/posthoc coordinate conversion and remove the posthoc dependency on calibration's
  private keypoint-name helper. Neither warrants duplicating scientific computation in FreeMoCap.
- Validate actual published output in the app, including camera geometry display, missing samples,
  switching recordings/results, and video/3D alignment. Automated reader tests do not cover these.

Target interaction: record, stop, choose processing settings, process, open playback, play/seek
original videos alongside reconstructed 3D data. This milestone does not require the encoded grid
video or all advanced restart controls. It does require truthful status and explicit errors.

- [ ] **1. Exercise a real recording through the existing processing entry point.**
  User-confirmed processing completion is done; the broader acceptance checks below remain tracked.
  Confirm capture finalization before processing; preserve recording ID and directory throughout.
  Run detection, triangulation/planar projection, identity filtering, global fit and reconstruction.
  Publish canonical output. Remove required CSV/NPY/Blender work from the success path.
  Use explicitly selected calibration geometry only when the requested computation needs it.
  Acceptance: complete input-frame coverage and plausible numeric output, including missing frames;
  imported videos without timestamps use SkellyCam's declared inferred timing.

- [ ] **2. Define and implement the minimal typed API boundary.**
  Extend existing services rather than adding a job system. Recording inspection returns committed
  run IDs, groups, channel/model descriptors, media/time mappings, time ranges and result revision.
  Fresh processing returns the existing transient pipeline ID; completion identifies the committed
  recording/run/revision. Progress and cancellation use the existing transport.
  Keep Python models and TypeScript types aligned through the project's type-generation path.
  Acceptance: API-level start, progress, completion and error tests against the real worker path.

- [ ] **3. Add canonical playback queries.**
  Implemented and covered by HTTP/reader tests. Real-output visual acceptance remains pending.
  Read an explicit recording/run and bounded recording-time interval with group/channel selection.
  Return descriptors and packed numeric arrays, not a JSON object for every tall scalar row.
  Reuse the live renderer's model/frame types; preserve names, nulls, units, quaternions and references.
  Resolve exact canonical paths, with no arbitrary-Parquet discovery. Support data without video.
  Acceptance: bounded reads select the intended run and preserve mixed-rate sample grids.

- [ ] **4. Wire the existing playback page and processing controls.**
  Canonical 3D provider is connected; finish controller/media mapping and app acceptance below.
  Replace the old file-layout adapter. Use recording time as the cursor; resolve each sensor group
  and camera via its own timestamps/media mapping. Frame stepping is scoped to a selected group.
  Show recording/result selection, pending/running/failed/cancelled/completed processing states and
  an Open playback action after publication. Key data caches by recording location, run and revision;
  cancel/discard obsolete seek responses. Do not change the committed view during processing.
  Acceptance: record -> stop -> process -> play/seek synchronized video and 3D in the running app.
  Reopening the app loads the same saved result without detector work.

## Milestone B: complete processing and reprocessing controls

- [ ] **5. Resolve saved prerequisites and stage signatures.**
  Expose point-only reads for refitting, independent of stale fitted results. Recompute expected
  group-stage signatures from actual saved inputs/settings; never trust stored signatures as their
  own validation. Add timing/observation/triangulation completion identities where needed.
  Represent identity filtering explicitly; define eligibility before adding gap filling/filtering.
  Acceptance: changes to points, model, timing, geometry or settings select the correct restart.

- [ ] **6. Wire execution plans into the existing worker manager.**
  Launch video/detector workers only for observation computation. Launch numerical workers directly
  for saved-data requests. Preserve SkellyCam/SkellyTracker/SkellyForge ownership of their operations.
  Acceptance: reconstruction-only execution with video opening and detector construction forbidden;
  keep/overwrite, early stop, cancellation and failed publication preserve unaffected results.

- [ ] **7. Complete preview/start and advanced UI controls.**
  Preview returns reusable/executed stages, invalidated outputs, resolved prerequisites and proposed
  target run. Start revalidates the same request and result revision under the recording lock.
  Reject stale previews; do not execute a changed plan silently. Expose keep/overwrite and advanced
  stage boundaries with clear consequences. Refresh playback by committed revision after success,
  retaining the time cursor when in range. Keep pipeline ID distinct from saved run ID.
  Acceptance: the displayed preview agrees with actual execution, including concurrent changes.

## Milestone C: agreed default video output and full acceptance

- [ ] **8. Implement the annotated `.freemocap.mp4` grid.**
  Reuse the UI overlay renderer on original frames and selected saved observations. Validate UI/export
  rendering agreement, encode the synchronized grid, embed selected metadata and native-rate data,
  and verify extraction. Apply the same keep/overwrite result identity and content-based validity.
  Report video generation separately from numerical success; never show stale exports as current.
  The raw grid and additional file formats remain optional follow-up exports.

- [ ] **9. Validate the complete workflow and failure cases in the app.**
  Fresh calibrated multicamera recording; single-camera planar processing without calibration;
  imported timestamp-free video; reconstruction-only restart; keep and overwrite; cancel/failure;
  app reopen; data-only playback; mixed 30/120 Hz fixtures and rapid seeks. Check bounded playback
  memory and long-recording publication costs. Full default-output completion requires both numerical
  publication and annotated-grid success.

## Estimate and sequencing

Working budget for one engineer/agent working through implementation, review and app validation:

- Milestone A: approximately **3–6 focused engineering days**.
- Milestone B: approximately **3–5 additional days**.
- Milestone C: approximately **3–6 additional days**; browser rendering/encoding is the least certain part.

These are planning ranges, not measured completion forecasts or promises about unattended agent
runtime. Re-estimate after the first real recording passes step 1. Camera/codec failures or substantial
worker lifecycle defects could extend them. No additional scientific features or non-identity
filtering are included in these ranges.

Recommended priority is A first, then B and C. This deliberately brings a narrow fresh-processing
app workflow forward from the broader backend-first acceptance sequence. It does not call advanced
reprocessing or the agreed default MP4 output complete before their acceptance gates pass.

Camera ownership cleanup: removed ResolvedCameraGeometry and its recording-only basis default.
Recording descriptors and execution inputs accept the calibration CameraModel directly. Camera classes
own JSON serialization; a regression verifies projection, Parquet round-trip, schema and equality.
Scale-fit and model wrappers remain the next separate review chunks. Saved camera descriptors use
the CameraModel structure; no compatibility adapter is supplied for the removed wrapper.


Lifecycle cleanup: see [pipeline lifecycle scopes](pipeline-lifecycle-scopes.md). Cancellation is
scoped by task/mode. Worker failures stop the owning pipeline; global shutdown remains explicit.
50 focused tests and frontend type checking pass. Real-app concurrent pipeline acceptance is pending.

