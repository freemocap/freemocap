---
mdx:
  format: md
plan_status: ongoing
plan_migrated: "2026-09-10"
---

# Annotation composition and media inputs

Status: source audit and proposal for review; no annotation behavior changed.
Parent work: mocap/posthoc media identity, processing stages, and recording outputs.

## Current behavior

- FreeMoCap `core/pipeline/posthoc/video_node.py::_build_annotator` selects a Charuco-only
  annotator whenever any Charuco detector is configured. Other observation stages are then
  ignored by that annotator. This is a concrete mixed-detector omission, not a confirmed
  reproduction of the user's previously observed video.
- SkellyTracker `core/annotation/keypoint_annotator.py` copies the input image once and
  traverses all stages and children on that same image. Its composition does not inherently
  discard earlier layers. Specialized Charuco drawing also copies the supplied image rather
  than reopening a raw frame.
- VideoNode decides to use existing annotated pixels solely because the output filename exists.
  It renames that file to a .prev path, reads it sequentially, and writes the destination.
  A failed/short base reader silently changes the input to raw frames. No explicit source
  relationship or requested composition policy governs that switch.
- The .prev file is deleted in finally, including after failure; the destination may then be
  incomplete. Composition and output retention are conflated, and concurrent writes are not
  coordinated here. No change to actual recording files was made during this audit.
- The live UI has a different renderer. ServerContextProvider appends detector overlays for
  a camera/frame, and the worker sends that combined observation to the generic skeleton
  renderer. The dedicated Charuco renderer receives null in this route. The generic name is
  misleading: its payload can contain several tracked subjects/models.
- Live rendering preserves base pixels when clearing its intermediate canvas: prepareCanvas
  redraws the supplied bitmap before overlays. However, flattening points by name loses model
  scope for connection lookup, and retaining the last observation across frames deserves a
  separate timing review. Neither is established as the cause of the reported disk-video issue.

## Proposed distinctions

1. Compose selected overlays for one exact camera/frame. Render every selected layer in an
   explicit order on the same image. Preserve stage/model/subject identity; do not assume a
   single person or select one annotator for an entire mixed observation.
2. Choose annotation input explicitly:
   - Regenerate: original video plus all selected saved observation/model layers.
   - Add overlays: explicitly selected annotated video plus additional selected layers.
   An existing file must not silently choose this mode. Burned-in pixels cannot support
   removing or replacing a previous overlay; those operations require regeneration.
3. Keep/overwrite chooses the output destination independently of the annotation input.
   Write a separate temporary output and publish only after successful completion. Failure or
   cancellation must preserve the selected input and any previously completed destination.
4. Adding overlays requires a verified frame-preserving relation to the original source,
   matching frame counts, and incremental decoding. Missing/corrupt/short input is an error,
   never permission to substitute raw frames partway through.

## Ownership and next chunk

SkellyTracker owns observation-annotation composition and its tests. FreeMoCap owns selecting
recording media/results, associating exact frames, scheduling the export, and publishing output.
SkellyForge remains the owner of model geometry/connections. The existing UI rendering cannot
be reused inside Python directly; sharing render inputs/style semantics versus running the UI
renderer for exports remains a design choice, not justification for another independent schema.

Recommended first implementation after review: fix mixed-observation annotation composition in
SkellyTracker and replace the exclusive factory choice in FreeMoCap. Test skeleton + board in one
frame, stage ordering, absent detections, and retention of existing base pixels. Then implement
explicit input/retention policies and tests for repeated rendering, frame mismatch, cancellation,
and concurrent output ownership. Keep per-camera exports provisional while developing the
.freemocap.mp4 grid export. Do not implement geometric camera permutation search in this tasklet.


## Composition implementation checkpoint

SkellyTracker KeypointAnnotator supports typed per-stage specialized annotators and composes their
returned image with generic stages and nested children in observation order. It preserves the
supplied base image content and rejects renderer output with a changed shape or dtype. Three
pixel-based tests pass, including actual Charuco and generic keypoint drawing in either order.

Dependency handoff: user commits/pushes SkellyTracker and updates FreeMoCap's Git dependency.
Then replace FreeMoCap's exclusive Charuco factory branch with configured stage composition.
No FreeMoCap annotation behavior has changed yet. Explicit input choice and output retention remain
subsequent work; existing-video layering has not been removed or changed.


### FreeMoCap composition integration

Verified the installed SkellyTracker compositor API. VideoNode now always uses the stage compositor and registers specialized Charuco drawing by the configured stage name, traversing nested configurations. It no longer selects a Charuco-only observation annotator for the entire tracker. An integration pixel test passes for sibling and nested body/board observations, a non-default board stage name, preservation of input pixels, and no mutation of the source image. Existing-video input selection and retention behavior are unchanged; those remain the next chunk. Test the actual mixed detector workflow before treating disk annotation QA as complete.


### Encoding and input checkpoint

VideoNode uses the installed SkellyCam PyavVideoWriter (libx264, CRF 18). AnnotationInput defaults to RAW; ANNOTATED is an explicit pipeline-construction option. Existing output does not implicitly select layering. Missing, unreadable, or frame-count-mismatched annotated input fails. Output is encoded separately and replaces the destination after successful decoding and encoder flush; selected input is closed before replacement. Cancelled runs do not publish partial output. Real encoded-video tests verify H.264, preserved frame count, raw regeneration despite existing annotations, explicit layering, and stage composition. UI/API configuration and keep-output destination selection remain to be wired; the application currently defaults to raw regeneration.

### Mocap board detection checkpoint

Target: a default-on board checkbox above the human detector settings, with AUTO layout selection
and the user's physical square length. Board absence is normal for mocap. Body detection processes
every frame. AUTO search skips 1, 2, 3, ... frames after successive misses, capped at 30 skipped
frames. The first valid board establishes one definition for all cameras in the recording.

Implemented in the local SkellyTracker checkout: CharucoBoardSelector.search_frame accepts an
ordered multiframe and lazily consumes camera images only when search is due. Selection locks
immediately; subsequent calls return the selected definition without further searching. Nine
selector tests pass, covering increasing/capped skips, non-consumption of skipped images,
first-match locking, actual board detection, and invalid frame order.

This is a dependency primitive, not application integration. User commits/pushes SkellyTracker
and updates FreeMoCap's Git dependency before consumer integration/testing. No editable install
or environment substitution is part of this handoff.

Remaining integration: coordinate recording-wide selection alongside camera workers; wire the
checkbox and board settings through the request; prevent board-only cached observations from
bypassing body detection; publish/reconstruct both selected model bundles instead of assuming
one human model; verify composed annotations and no-board recordings in the real app. Do not
resolve AUTO independently per camera or run the calibration task implicitly.

### Consumer prerequisite and worker coordination review

Verified FreeMoCap's installed Git dependency exposes CharucoBoardSelector.search_frame.
Board-cache reuse now requires one independent Charuco stage with no additional detectors,
children, or object detector. Cached stage structure must match the requested structure. A
board-only cache cannot substitute for mixed body/board processing. Four focused tests pass,
including sibling/nested/mixed-detector configurations, annotation composition, and video encoding.

The default-on checkbox is not yet wired. Current PosthocPipeline creates independent video
workers and binds the reconstruction configuration before detection. Recording-wide AUTO cannot
be added by letting each worker independently select a board: detector definitions and the
reconstructed board could disagree. The selector primitive alone does not solve coordination.

Recommended next design checkpoint: use the existing Tracker.process_batch capability at a
synchronized camera-group processing boundary. One owner supplies sequential multiframes to
the selector, locks the board once, and configures the matching board stage/model while human
processing continues every frame. Review worker ownership, cancellation, bounded image memory,
annotation composition, and propagation of the resolved definition to reconstruction before
changing that boundary. Reuse existing tracker batching and annotation machinery; do not build
another detector implementation or independent camera-selection protocol. Calibration remains a
separate task. No worker-layout change has been implemented at this checkpoint.

### Shared detection implementation checkpoint

`freemocap/core/pipeline/posthoc/mocap_detection.py` implements the recording-group detection
iterator. One owner reads each camera sequentially through SkellyCam's reader and calls the
installed SkellyTracker batch API. One selector searches the group with capped backoff; the
first match configures the existing Charuco tracker for every camera, preserving the user's
square length. Body processing runs every frame. Explicit layout and disabled board tracking
bypass AUTO; no board is a normal outcome. ExitStack releases readers and tracker sessions on
completion, iterator close, cancellation, and errors. Detector implementations remain in
SkellyTracker. The iterator retains no recording-wide image cache.

ObservationBuffer now aligns measurements to an explicit stage-qualified name axis. Batch
triangulation obtains that axis from all cameras and all frames, not frame zero. Absent or
invisible measurements stay NaN; mismatched camera frame sequences fail. This supports a board
first detected later without inventing detections for earlier frames.

Validation: seven recording-group tests use encoded video and actual Charuco detection (body
inference is substituted to avoid model downloads), covering late selection, shared geometry,
no board, disabled/explicit modes, cancellation, iterator close, and detector failure. Five
alignment tests cover late/reordered points, cross-camera name alignment, missing schema names,
frame mismatch, and actual single-camera planar reconstruction. Six calibration preparation
tests and four cache/annotation/encoding tests also pass.

The live Mocap worker and UI still use their existing route. Next: integrate this iterator into
the managed Mocap worker lifecycle; reuse the annotation writer rather than duplicating its
encoding/publication logic; pass the resolved board into shared multi-model reconstruction and
Parquet publication; wire the default-on checkbox and shared board settings through the API.
Keep calibration on its separate pipeline. Real-app QA follows this integration, including
body+board overlays, no-board success, and pipeline-scoped cancellation/failure.

### App-testing handoff

The default-on **Detect and reconstruct Charuco board** control is wired through Mocap's
persisted settings and both recording/processing request paths. It shares the existing board
layout and user-entered square length settings. Board mode is a shared tracking enum in Python,
not a calibration-task dependency.

MocapPipeline now owns one managed worker for synchronized batch detection, annotation, and
the existing reconstruction/publication task. It uses the installed SkellyTracker batch API;
calibration retains its separate task and camera workers. Terminal progress is retained and
worker failure signals only the owning pipeline. Detection progress describes synchronized
multiframes. Readers advance incrementally and verify the declared end of each video.

Both tasks use AnnotationVideoOutput and build_observation_annotator. Encoding, explicit input
selection, temporary-file cleanup, and publication have one implementation. The normal Mocap
workflow regenerates from raw pixels with all selected overlays. Shared reconstruction receives
both human and selected board bundles; no detected board produces a human-only result. Physical
board dimensions remain user-supplied.

Mixed detection is described by a Mocap tracker source in Parquet. Reconstruction sources
explicitly identify that input source; detector type describes the model rather than implicitly
identifying its input stream. Completion validation and saved reconstruction use this explicit
association. This was verified by publishing and reloading the board reconstruction.

Validation: 29 focused unittest cases pass, including encoded-video detection, optional board
publication, saved reconstruction, cancellation preserving previous annotations, and a real
Windows-spawned worker's scoped failure. TypeScript type checking passes. Additional manual
smoke runs used cached real RTMPose/YOLOX models: a complete single-camera recording through
annotations and Parquet, and multicamera batch detection. No dependency installations or Git
mutations were performed. Existing pytest-based tests are not included in this count because
pytest is not installed in the FreeMoCap environment.

Real-app checks:
1. Restart normally. Open a recording in Playback, then Mocap processing / Detector Settings.
   Confirm the board control defaults on. Choose AUTO and enter the measured square length.
2. Process synchronized videos containing a person and board with the appropriate calibration
   selected. Verify completion and fresh playback annotations with both overlays.
3. Disable the board control and rerun: body processing remains active and regenerated
   annotations contain no board overlay. Re-enable it and process footage without a board;
   absence must not fail Mocap.
4. Cancel during detection and verify the app/realtime pipeline stays responsive. A subsequent
   rerun must complete. Also verify the separate calibration workflow still completes.

Separate runtime follow-up: installed ONNX Runtime advertises TensorRT but cannot load
`nvinfer_10.dll` in the test shell; its existing provider fallback selects CUDA and completes
inference. SkellyTracker's provider selection/reporting owns that issue. No environment or
provider-policy workaround was added here. App testing should distinguish this diagnostic from
an actual Mocap pipeline failure.

### App-test follow-up: launch errors and terminal progress

- Corrected the application Mocap factory return type so runtime validation accepts the launched MocapPipeline.
- Failed worker startup cleans up the pipeline; Mocap worker exit without a terminal outcome becomes FAILED.
- Operation errors wrap in an in-flow banner rather than overflowing a fixed toast.
- SkellyCam source correction: FullTimestamp.__repr__ returns its string, allowing diagnostic formatting. Requires the normal commit/push/dependency-update workflow; installed dependencies were not modified.
- Validation: Mocap integration tests, application runtime-boundary test, unexpected-exit test, and UI TypeScript check.
- App QA: restart backend normally, launch Mocap, verify launch succeeds; trigger a detector/input failure and confirm terminal error, cleared running progress, and unrelated realtime/calibration availability.

Architecture correction: the single-worker Mocap execution path is slated for replacement. See [Mocap multiprocessing alignment](mocap-multiprocessing-alignment.md) for the audited topology, proposed reuse boundaries, and review checkpoints. Further app-test readiness depends on that correction.
