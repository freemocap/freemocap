# Shared skeleton presentation

Implemented and validated on 2026-11-01 in the editable `sfn26` Core/Forge
checkouts. Changes are unstaged; the owner runs the final visual app assessment.

## Ownership and behavior

Forge owns the authored presentation declaration, the selected superquadric
compiler, geometry validation, and snapshot round trips. Core projects its
prepared local lines, surfaces, and materials into optional `ModelDefinition.presentation` metadata.
Playback restores the recorded definition and uses the same model projection
as realtime. No additional detector mapping or per-frame skull fit is introduced.

The selected human has five 64-edge skull contours (vertical exponent 1.0,
horizontal exponent 0.85, posterior depth 0.8), pelvis rim/hip-socket struts,
and xiphoid/SC/acromion-to-chest-center connections. The ear-to-nose section lies
in the plane through both ears and nose. The nose directs the front intersection
without deforming the skull volume. A translucent shell and curved ear-side caps
support the landmarks visually; there is no modeled nose or detailed jaw.
Forge's research note and bibliography document
the construction and its assumptions.

The shared `ModelConnectionRenderer` prepares attachment rows and local vertices
on definition/layout changes. For dirty frames it writes transformed endpoints
into the existing line buffer. The transform is:

`world = segment_origin + world_rotation * local_vertex * (segment_length_mm / authored_length)`

If the length channel is absent, a measured instance scale may supply the scale.
A present invalid length, missing origin/world quaternion, or invalid scale hides
the contour. No arbitrary default size or second rest rotation is applied.
No fitting, trigonometry, name-map construction, objects per vertex, or additional
geometry/material allocation occurs in the new renderer update code.

Contours follow the existing **bone lines** visibility control. Presentation
exclusions hide skull/pelvis solid glyphs and replaced origin spokes. Scientific
segments, parenting, landmarks, axes, and picking-slot identities remain intact.
Other bone glyphs keep the existing **bones** control. No new draw object/material
is introduced for the contours.

Selected materials: contours `#73747a` at 0.75 opacity, thorax/pelvis lines
`#73747a` at 0.75, shell `#444b61` at 0.21, side caps `#5f6063` at 0.25.
Thorax and pelvis connections now match the skull outlines in both color and
opacity. Surfaces retain their
darker colors; opacity and geometry are unchanged. Sided skull landmarks use the same
standard muted blue/red styling as body landmarks. Explicit skull, spine and
pelvis midline landmark groups use `axial_landmark` purple `#84609f`. These groups
do not recolor connection lines or surfaces.
Raw keypoints, mapped keypoints, and reconstructed landmarks start hidden in
the shared 3D viewport; their existing toggles remain available.
Native RGBA line attributes retain one line batch. The shell (561 vertices) and
combined caps (576 vertices) add two static indexed meshes, 2,048 triangles total,
per person. Dirty frames update only their rigid matrices and visibility. They
share the contour's pose/scale validation and bone-lines visibility control.
Geometry/materials are disposed on replacement and unmount; translucent surfaces
do not write depth, and side caps use a single double-sided pass.

## Transport and compatibility

### Independent face layers

The tracked-model panel now separates **Face keypoints** (the former mislabeled
Face outline toggle, still initially on) from **Face connections** (initially
off). Both use the same live/playback `FaceRenderer`. Connections previously
failed because the UI expected obsolete names such as `face.lips_61`, while
current Tracker schemas emit `face_0061`. The obsolete UI topology table is removed.

Tracker remains the topology owner. Core carries its existing profile connections
through `TrackedSkeletonBundle`, `RecordedModel`, and shared `MessageComposition`
into optional static `ModelDefinition.tracker_connections`. New recordings preserve
those edges; old recordings without them keep face points without invented edges.
Absent topology is omitted during legacy model serialization, preserving previous
recorded-model fingerprints. No numerical channels, reconstruction algorithms,
viewport frame layouts, or transport repetition rules change.

The renderer prepares integer point/edge rows only when names or model definitions
change. It reuses one point buffer and one line buffer, compacts valid endpoints,
and updates only dirty frames. The worker reads its existing packed coordinates;
direct sources use the existing reusable packing workspace. Missing detections
hide empty batches. Toggles share preparation but independently control updates
and visibility; both off unmounts and disposes all face resources. Face connections
require one additional draw call when present, not one object per edge.

Validation: 32 focused Python tests, 27 TypeScript tests, full UI typecheck, and
11 production playback browser tests passed. Both reference recordings display
68 face points and all 65 RTMPose face connections with the correct Tracker
topology supplied to the test-only metadata override. Twenty cycles through all
four toggle combinations preserve visible geometry and stable resource counts.
Numeric transfer parity remains exact and model frame buffers remain 8,304 bytes.
Both reference benchmarks pass the existing p95 update/submission gate; the
largest submission increase is 0.1 ms, at browser timer resolution. These reports
are `face-test.json` and `face-sample.json` under `.test-artifacts/skull-display/`.
They compare full selected display against a legacy display, so their three added
draw calls include two skull surfaces and the one face-connection batch.

Restart the backend and refresh the frontend after this code change: an already
loaded Python composition cannot acquire a new metadata field from UI refresh alone.

### Self-describing messages

The [self-describing message protocol](current-work-plans/03-transport/message-protocol.md)
is unchanged. Every server frame carries its full interpretation metadata.
Repeated metadata bandwidth is an accepted architectural tradeoff that prevents
server/client state mismatch. This feature uses the existing connection-owned
`MessageDecoder` validation/identity cache, `TransportService` reconciliation,
change-driven static-model subscriptions, and pooled numerical worker transfers.
There is no delta protocol, out-of-band prerequisite, or new dynamic channel.

Before the surface extension, an isolated model-only CBOR probe measured 21,266 bytes for legacy-like display
metadata and 39,846 bytes with these visuals: 18,580 additional static bytes per
self-describing packet. This is not additional numerical worker data. The probe's
encoding medians were approximately 0.96/1.69 ms while reference replay was active;
they are not end-to-end application latency or a transport redesign justification.

With the selected surface extension, a model-only CBOR probe is 86,302 bytes;
the two surfaces account for 46,324 bytes. This remains prepared static metadata
inside each self-describing packet. Numerical worker-frame size is unchanged.

New runs record the new declaration and SC geometry. Old snapshots without
presentation metadata retain their recorded geometry and legacy display. Opening
an old recording does not silently apply current anatomy. Saved-stage replay
continues to honor the saved model; create a fresh processing run to adopt current
defaults. No existing recordings were rewritten.

The SC adjustment is a geometry change: bilateral anterior offsets are 70% of
their prior value. In the authored rest pose, the unchanged hierarchy propagates
a posterior translation of `0.0145779 * body_height` to clavicles and downstream
arms. The initial integration left the notch unchanged; the correction below
brings it to the same depth as the paired joints.

## Validation evidence

### SC alignment correction — 2026-11-01

The notch now shares the paired SC joints' anterior depth, `0.0340151` (70% of
`0.048593`). MediaPipe and RTMPose body mapping coefficients were recalculated
from the current reference pose for both SC joints, the notch, and xiphoid.
For shoulder midpoint M, shoulder width W, and each orthonormal body axis A,
the coefficient is `dot(P - M, A) / W`. This includes the hip-to-shoulder tilt
and the acromion translation caused by the changed SC attachment. Multiplying
old coefficients by 0.7 would incorrectly apply part of the change twice.

Core tests compare scalar and prepared dense mappings with Forge reference
landmarks under rotation, translation and three scales for MediaPipe, RTMPose,
and RTMW/MediaPipe-hands presets. Tracker retains standalone ownership of its
mapping constants; Forge owns geometry. No numerical frame-path code or transport
changed. This establishes reference calibration, not zero residual between noisy
observations and a fitted model in every live frame.

### App-assessment follow-up — 2026-11-01

Added hips-center-to-socket connections, the two sacroiliac-to-coccyx edges that
close the sacral kite, and chest-center-to-sacrum-top. Xiphoid anterior depth is
now 60% of its previous value (`0.078964` to `0.0473784` authored units); its height
and all other rest landmarks remain unchanged. SC remains at 70%. Construction
contours use 60% of the existing side-color brightness, prepared once per layout.

Live camera pause now forwards the existing camera pause state to the viewport's
presentation buffers. It suspends their one-second expiry while keeping the current
owned frame buffers available for rendering and inspection. Resume restarts the
normal grace interval; incoming missing values still replace prior values, and
reset/teardown still releases buffers. This does not change server messages,
reconstruction retention, recording data, or playback's existing held-frame behavior.

Focused follow-up validation: 20 Forge tests, one Core snapshot/projection test,
19 TypeScript tests, three real-browser worker tests, and full UI typecheck passed.
The pause regression holds frame identity and buffer ownership for a simulated
five minutes, then verifies resume, replacement, expiry, and teardown. Physical
camera interaction remains for the owner's app assessment. The broader
measurements below describe the original integration, before this follow-up.

### Original integration

Reports are in this checkout's ignored `.test-artifacts/skull-display/`.
Fresh numerical-profile references are in `C:/tmp/fmc-skull-1101/`; they were
processed through `python -B -m freemocap.tools.datasets process-all`, using a
short temporary path because the framework's Windows video-path check rejected
the nested workspace path. No dependency installation or Git mutation was used.

- Both fresh posthoc references completed: 222 and 1,108 frames.
- All 16 standard realtime replay cases passed: both references, both inference
  placements, explicit/latest calibration, board-only/board-plus-human tracking.
  Tests verify source-frame timing, live settings changes, reconstruction, worker
  shutdown, shared-memory release, and unchanged reference hashes.
- Both existing saved-stage reference tests passed: raw data, timing, reference
  frames and scale-fit preservation, deterministic reconstruction reruns, and
  unchanged source files.
- Production browser playback suite: 10 passed. Its stale retained-missing-value
  expectation was aligned with the existing immediate-clear policy; no production
  retention behavior changed.
- Forge numerical/hydration/snapshot/loading suite: 79 passed. TypeScript
  prepared/transfer/receive-reuse suites: 43 passed. Core projection/playback suite:
  15 passed; relay/projection/composition-cache suite: 10 passed (overlapping tests).
  Full UI typecheck and citation validation passed. Commands are recorded in the
  task checkpoint and reports.
- Actual production renderer output agrees before/after the viewport codec.
  Missing-pose recovery, equal-size model replacement, picking identities,
  visibility unmount/remount, and two-instance preparation were checked.
- The exact original legacy reference retained identical file hash, every decoded
  channel fingerprint/timestamp, and sampled renderer geometry after this change.

`final-test.json` and `final-sample.json` record five alternating paired display
comparisons on identical numerical frames. The test baseline removes only the new
display declarations; SC numerical values remain identical within each pair.
Both workloads pass the gate of `max(5% of baseline, 0.2 ms/frame)` for added p95
renderer-update and WebGL-submission time. Draw calls remain five. Twenty repeated
model/visibility cycles retain five visible/three hidden GPU geometries, two
programs, and four picking meshes with no growth.

Separate real-worker receiver/store passes have p95 round-trip time of 0.10 ms
for the selected visuals, unchanged 8,304-byte numerical frames, at most two
allocated buffers, and every packet returned on teardown. Neither mode recorded
a round trip over 33 ms in those passes. These are unpaced transfer measurements,
not physical-camera GUI frame-rate or GPU-completion measurements. Browser timer
resolution limits interpretation of sub-0.1-ms differences. Full-process peak
memory and final subjective appearance remain outside these measurements.

## Review boundaries

The surface/alignment extension passed 64 Forge tests, four Core projection and
mapping tests, 31 TypeScript tests, full UI typecheck, and 11 production playback
browser tests. Surface vertices and ring samples satisfy the implicit equation;
the ear crossings and projected nose direction are checked numerically. Legacy
recipes retain their old ring and no surfaces.

`surface-test.json` and `surface-sample.json` apply the current display metadata
to the same 222/1,108-frame reference values in the benchmark only. Both pass the
existing p95 update/submission gate; differences are below the browser's 0.1-ms
resolution. Maximum draw calls increase from five to seven. Twenty lifecycle
cycles hold seven visible/three hidden geometries, four programs, four picking
meshes. Direct/worker-transferred geometry matches, and numerical frames remain
8,304 bytes. Missing skull poses correctly remove both surface draws. These are
renderer/transfer measurements, not physical-camera FPS or GPU-completion timing.

- Forge: declaration/compiler, human connections and SC offset, snapshot support,
  numerical tests, and mathematical provenance.
- Core: generic static projection, shared prepared line rendering/glyph exclusion,
  tests and extensions to the existing benchmark; transport strategy is unchanged.
- Workspace/Core agent guidance: require understanding architectural intent and
  existing repetition handling before proposing subsystem changes.

All work remains unstaged and uncommitted; unrelated existing edits are preserved.
