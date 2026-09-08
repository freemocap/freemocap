# Camera and media identity audit

## Status — 2026-09-08

The cross-repository source audit is complete for media identity. The final SkellyCam
path/URL changes still require the normal commit, push, dependency update and integration
check. Geometry matching is a separate, unimplemented next step; identity cleanup does
not prove which physical camera produced a video or that a calibration is still valid.

The user has accepted the current Windows playback, calibration and mocap workflows.
Playback optimization is closed for this pass. Presentation may be slightly offset between
native video elements; the collapsed warning explains checking embossed frame numbers.
Processing still requires synchronized videos with equal frame counts, without comparing
reported floating-point FPS values.

## Identity contract and ownership

| Concern | Owner and current rule |
|---|---|
| Recording identity | The complete recording folder name, including dots. Paths locate recordings; they are not physical camera identities. |
| Capture device labels | SkellyCam device detection/configuration. Labels and indexes are scoped acquisition identifiers, not persistent proof of physical identity. Collisions must surface. |
| Video file identity | The full filename including extension within its recording/video location. Arbitrary imported names remain valid; no camera ID or index is guessed from a name. |
| Declared source relationships | SkellyCam `VideoAssociations` and `RecordingInfo` publish/read explicit source-to-file relationships. Duplicate ownership and conflicting declarations fail. |
| Relative file paths | SkellyCam `recording_metadata.py` validates and normalizes declarations and enforces recording containment. Nested Windows/POSIX separators resolve consistently. |
| Import and synchronization | SkellyCam `VideoCopyPlan` and synchronization producers retain explicit relationships and reject destination collisions before copying. Forward filename formatting is allowed; reverse filename inference is not. |
| Derived annotations | SkellyCam `VideoDerivation` describes the originating source and frame relationship. A suffix is a display/output name, not evidence of ancestry. |
| Timing | Declared source timing is preferred; absent timing is inferred from frame order and nominal FPS. Playback media each carry their own timeline; there is no duplicate source-only timestamp map. |
| Playback inventory and UI | FreeMoCap composes independently loadable resources. An invalid reconstruction cannot suppress viable videos. Raw/annotated media use the same playback machinery. URL segments are escaped and explicit recording parents preserved. |
| Detector and kinematic computation | SkellyTracker and SkellyForge consume supplied identities. Neither owns video filename parsing or physical camera association policy. Webcam indexes in tracker demos are acquisition choices. |
| Calibration assignment | Pending geometry work. Existing ID/index binding is an input assumption, not a geometric validation result. |

## Audit coverage

Reviewed capture publication, device labels, import/copy/synchronization, video loading,
recording metadata/timing, annotation derivation, standalone SkellyCam playback endpoints,
FreeMoCap playback inventory and frontend consumers, task recording construction, Blender
output naming, recording status, tracker demos and Forge production code.

The production sweep found no remaining `ParsedVideoFilename` / `parse_video_filename`
consumers or reverse filename camera-ID parser. Remaining uses of video stems generate
output names or labels. Date parsing in the recording sidebar is presentation sorting.
Numerical camera indexes inside calibration algorithms are ordered array slots.

Final corrections in this pass:

- Preserve dotted recording folder names in mocap/calibration requests, Blender output and status.
- Remove the unused bundle timestamp dictionary that collapsed raw/annotated source timelines.
- Consolidate relative-path rules for video associations, derivation and timing resolution.
- Correct standalone SkellyCam recording containment and returned video URL encoding/context.

## Verification and release boundary

- SkellyCam association, derivation, metadata and timing tests: 29 passed.
- FreeMoCap bundle and recording association tests: 6 passed.
- FreeMoCap UI TypeScript check passed.

SkellyCam tests use its own environment. FreeMoCap tests use its configured Git dependency,
not the edited sibling checkout. No editable install or dependency source substitution is used.
After publishing and updating SkellyCam, rerun the focused integration checks and smoke-test
opening a recording, raw/annotated switching, and starting mocap/calibration from playback.
Linux/macOS packaged playback remains a separate portability check.

## Next: camera geometry matching design

Agree on one assignment policy shared by live and recorded consumers before implementing it:

1. Separate source labels, physical-camera evidence and ordered solver slots explicitly.
2. Reuse existing camera models and projection/triangulation primitives.
3. Plan reprojection-fitness evaluation of candidate permutations, including coverage,
   ambiguity, candidate limits and failure reporting. This search is new functionality.
4. Do not reinterpret a matching ID or index as proof of correct geometry, and do not
   recalibrate each permutation to conceal an incorrect assignment.
5. Require geometry only for operations that use it. Calibration remains a separate task;
   mocap consumes the resulting calibration artifact.

Then resume the Mocap/posthoc endpoint-to-worker walkthrough, stage reprocessing and
keep/overwrite semantics, ending at the recording output contract. Recording metadata
stays separate from model measurements; scientific outputs remain centered on Parquet
until their export contracts are agreed.
