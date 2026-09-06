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
