# Camera and media identity audit

2026-09-07. Static cross-repository audit; no runtime verification or implementation changes.
Reviewed repository history, the media-identity plan, architecture review, recording proposal,
and current producers and consumers. Snapshot: FreeMoCap `4c292aa9`, SkellyCam `4709a0d7`,
SkellyTracker `c29d9ec`, SkellyForge `5fe45aa`.

This audit precedes resuming the Mocap/posthoc request walkthrough. Identity policy crosses capture,
import, calibration, recording publication, playback, and both applications. A request-local fix
cannot establish the required contract.

## Findings

### App QA gate: realtime performance

Camera-only display is smooth, but enabling realtime mocap drops displayed throughput below
10 fps. The cause is not yet established; do not proceed to geometry matching while this is open.
The inference scheduler now rechecks queued work before sleeping after lease retirement, preventing
a missed notification from adding a 50 ms idle wait. A deterministic retirement/submission regression
test covers this race. Thirteen scheduler and live WebSocket tests pass.

Live frame delivery reports actual sent FPS and mean source/wait, composition, encoding, and send
durations every five seconds. Next app check: camera-only for 15 seconds, then realtime mocap for
30 seconds; capture these summaries alongside pipeline timing and displayed FPS. A small synthetic
composition/serialization profile measured approximately 3.6 ms per frame under cProfile; this is
not a measurement of the full live payload or proof of the slowdown's cause.

Paths below are relative to the named repository. Findings describe static code behavior and risks;
they do not assert that every exposed path is exercised by the current FreeMoCap UI.

### Capture and file identity: SkellyCam

- `skellycam/core/device_detection/detect_cameras_devices.py`, `CameraDeviceInfo.camera_id`:
  identifiers use a four-hex-digit hash of a device path or vendor/product/index, with an index
  fallback. They are useful device hints, not proof of physical camera identity or unchanged geometry.
  Truncation permits collisions; device enumeration/path changes can change the identifier.
- `skellycam/core/recorders/videos/parse_video_filename.py`, `ParsedVideoFilename.from_path`:
  canonical parsing falls back to camera-like words and embedded numbers, then the whole stem.
  Unknown indices become `-1`. A date or arbitrary name can therefore acquire camera semantics.
  `parse_video_folder` also reassigns ambiguous indices alphabetically. The sweep found no production
  caller of that folder helper; the per-file parser remains actively used.
- `skellycam/core/recorders/videos/recording_info.py`, `RecordingInfo.save_to_file`,
  writes camera configurations, but not the `videos` association that
  FreeMoCap's loader looks for. Capture therefore does not write the explicit contract that the
  downstream manifest reader expects.
- `RecordingInfo.video_file_path_from_camera_config` searches a generated stem with any extension
  and returns the first existing match. Multiple matching artifacts are not an explicit selection.

Forward filename generation is useful. Reverse filename interpretation must not establish a
scientific association merely because a string happens to resemble an ID.

### Processing and import: FreeMoCap

- `freemocap/core/pipeline/posthoc/video_group_helper.py`: the normal path rejects duplicate parsed
  IDs and ambiguous indices, which fixes earlier silent dictionary loss. However, `VideoMetadata`
  still derives its camera ID from its filename. `from_manifest_videos` keys the group by supplied
  IDs while retaining metadata with filename-derived IDs. The same video can consequently have two
  answers to "which source is this?" depending on the accessor.
- The same file's `_load_manifest_videos` tries two metadata names and falls back after unreadable
  JSON or absent mappings. Missing associations and invalid declared associations need different
  outcomes; invalid declarations must not silently turn into filename guesses.
- `freemocap/api/http/mocap/mocap_router.py`, `_check_video_sync`: independently parses names and
  repairs unknown/colliding indices by enumeration. A frame-count inspection should not manufacture
  camera identity, especially when the subsequent processing loader rejects the same ambiguity.
- Its import path associates synchronization results by removing `synced_` and matching stems.
  It copies imports by basename, or normalized stem plus `.mp4`, without destination-collision
  validation in that path. Distinct source files can target the same output name. This is a concrete
  data-loss risk and should be addressed before expanding import behavior.

### Playback and timing: both applications

- `freemocap/api/http/playback/playback_router.py`: the bundle uses identity-free batch probing,
  but still constructs filename-derived camera metadata to find timing. Annotated relationships
  are reconstructed by removing `_annotated`. Other routes match timestamp files by substring.
  The bundle's full-filename video identifiers also coexist with stem-based stream URLs/lookups.
- The bundle creates a timestamp dictionary keyed by timeline source alone. That projection loses
  distinctions available in the group/source media representation and needs explicit collision
  handling before supporting repeated source names or multiple groups.
- `skellycam/api/http/playback/playback_router.py` independently discovers stem-keyed files, parses
  camera IDs, and searches timestamps by substring. It is still mounted under `/skellycam` by
  FreeMoCap, alongside `/freemocap` playback routes. It is not simply unreachable source code.
- That SkellyCam router's video-serving route still calls `_ensure_web_compatible`, which can create
  `.web.mp4` files. This is separate from the current FreeMoCap WebSocket playback path. Its continued
  availability conflicts with the intended removal of disk-transcoding playback behavior and needs
  explicit cleanup, including checking the standalone SkellyCam frontend consumers.
- `freemocap/core/pipeline/posthoc/video_node.py` also associates recorded timing and cached realtime
  observations by camera ID and converts connection frame ordinals into recording ordinals. These
  joins must participate in the audit's replacement contract, not remain a separate cache policy.

Playback must keep independently viable resources available. An invalid reconstruction is an error
for that resource, not permission to hide videos. Ambiguous timing should be reported; absent timing
can use the agreed ordinal/FPS inference. Neither case justifies guessing a physical camera.

### Calibration and geometry: FreeMoCap

- `freemocap/core/tasks/calibration/shared/calibration_camera_binding.py` implements live binding:
  exact IDs first, then a constrained index mapping, with protections against partial/conflicting
  assignments. This is meaningful existing machinery to reuse, not replace with a parallel resolver.
- `freemocap/core/tasks/triangulation/triangulator.py` and
  `freemocap/core/tasks/mocap/posthoc_mocap_task.py` instead resolve geometry by requested camera IDs.
  A caller can therefore encounter different matching policies for the same physical setup.
- Array-based triangulation depends on camera order; its supplied-order check is valuable. A resolved
  association must carry consistent ordering all the way to array construction. Local array position,
  device index, and physical camera identity are not interchangeable.
- Matching identifiers alone cannot establish that a camera has not moved. Geometry assignment and
  geometric fitness are separate from identifying a file or opening a device.

The reprojection-fitness permutation search remains **unimplemented and on the roadmap**. Design its
candidate limits, observations, score, acceptance and ambiguity rules before implementation. It must
test assignments against fixed geometry, not conceal a bad assignment by recalibrating it.

### Recording descriptors and domain ownership

- `freemocap/core/recording/result_processing/observation_inputs.py`, `CameraRecordingDefinition`,
  combines a camera ID, a video filename and timing facts; `source_name` is `camera:{camera_id}`.
  Publication uses those names in a run-wide source dictionary. This embeds the current media/camera
  association in the proposed scientific model. Resolve scope and relationship semantics before
  freezing the descriptor or Parquet contract.
- `freemocap/core/recording/playback_queries.py` reads these definitions to recover media. This is
  another consumer of the association, alongside filesystem discovery; it must not define a competing
  fallback policy.
- SkellyTracker's searched camera-index references concern webcam/demo acquisition. The inspected
  shared-session machinery manages inference resources, not video-to-geometry matching. No production
  filename-to-calibration matching was found in this sweep.
- No camera/media identity matching was found in SkellyForge's production package. References to
  cameras and calibration describe scientific models, not filesystem associations. Keep that boundary.

## Preserve the good separations

- SkellyCam `VideoFileMetadata` and `probe_video_files` inspect media without inventing camera identity.
  Commit `09c30966` introduced that shared probe; current FreeMoCap consumes it. The remaining problem
  is callers applying identity guesses afterward.
- Playback's `view{index}` transport IDs identify ordered display slots. File identity used for cache
  freshness is also appropriate. Neither needs to become a physical camera ID.
- Existing `CameraModel`, timing readers, sequential video readers, observation types and shared
  transport should remain the implementation primitives. This audit does not propose another asset
  database, geometry wrapper, or ID for every concept.

## Contract to settle before implementation

Distinguish these meanings without automatically creating a class for each:

| Meaning | Required rule |
| --- | --- |
| Device handle/index | Local acquisition address; not persistent physical proof |
| Recording source | Scoped identity of the captured stream |
| Media file | Concrete representation of a source and frame range |
| Raw/annotated relationship | Explicit shared source and frame correspondence |
| Sampling group | Shared frame ordinal; current mocap requires equal frame counts |
| Timing | Recorded association or explicit inference; not a substring search |
| Geometry assignment | Validated source-to-existing-camera-model association |
| Transport slot | Request/session-local ordering only |

Metadata supplies declared relationships and evidence; it does not prove physical identity. Arbitrary
external filenames must remain usable. An unresolved association is acceptable until an operation
requires it. Fail that operation clearly rather than inventing an answer or blocking unrelated data.

## Cleanup sequence

1. **Agree the capture/import association contract.** Specify the minimal source/media/timing facts
   and their scope using existing models where possible. Resolve how supplied associations are
   validated and how arbitrary imports remain explicitly unresolved. Do not lock in a new folder
   layout or duplicate scientific metadata to accomplish this.
2. **Implement producers and consumers together.** SkellyCam owns recording/media primitives;
   FreeMoCap owns cross-domain orchestration. Cover capture, import, both playback APIs/frontends,
   observation reuse, publication and calibration input. Remove superseded filename guesses and
   parallel routes rather than adding compatibility fallbacks. Prevent collisions before any copy.
3. **Unify geometry-binding policy.** Reuse and clarify the existing binding implementation, keep
   scientific consumers supplied with resolved ordered geometry, and preserve independent calibration
   task execution. Decide the fitness-search design here before writing its new code.
4. **Resume the Mocap/posthoc walkthrough.** Review API requests, stage prerequisites, workers,
   publication and recording output using the settled relationships. Then finalize Parquet descriptors,
   stage reprocessing, keep/overwrite, and deliberate exports.

Acceptance cases must include arbitrary and duplicate stems, identical basenames from different
directories, malformed versus absent metadata, raw/annotated correspondence, multiple sidecars,
device reorder/reconnect, ambiguous geometry, reordered arrays, inferred timing, and partial playback.
Current synchronized mocap validation checks frame counts, not equality of floating-point FPS values.

## Limits and follow-up

### Implementation checkpoint: declared capture videos

App-QA gate, 2026-09-07: the updated Git dependencies pass 34 annotation/playback/import/association
integration tests, plus four publication/preflight/composition tests and four subtests. FreeMoCap's
TypeScript check passes. Timing fixtures now declare their file references; the preflight test targets
the current MocapPipeline factory. Geometry matching remains unchanged. Pause implementation for the
following real-app checks before beginning geometry work.

1. Make a short fresh recording. Confirm it appears in playback without a page refresh; play, seek,
   step and pause its raw videos. Verify all views show the same frame ordinal.
2. Run calibration on that recording with the correct board and square size. Inspect newly generated
   annotations; switch raw/annotated at a paused frame, then during playback. Position must persist.
3. Run Mocap processing using that recording's calibration. Verify annotations refresh, both layers
   appear when layering is selected, and playback plus reconstruction remain usable.
4. Repeat annotation generation with overwrite. Check the recording folder for unexpected duplicate
   outputs or partial files. Newly generated annotations use `<original filename>.annotated.mp4` and
   embed their source relationship; pre-existing untagged annotations remain independent media.
5. Import videos with arbitrary names and no timing sidecars. Playback and board detection must work
   with inferred timing. Do not test automatic assignment to an unrelated calibration in this pass.
6. On disposable test data, rename the recording folder and verify the new metadata's relative timing
   and video relationships still work. Corrupt a derived Parquet output and verify videos remain
   available with a bounded resource error. Do not corrupt a recording you want to preserve.

Report the first failing action, selected recording, and relevant logs. Do not start geometry matching
until this gate is accepted. Automated validation does not substitute for these real-app checks.

Closure candidate: the previous annotation/playback integration passes (19 tests plus two subtests),
and FreeMoCap TypeScript passes. Playback media now carries its variant explicitly; backend and UI
joins include variant plus filename. Capture writes relative camera/multiframe timing references;
readers locate recording metadata independently of the folder's current name. Missing declarations
permit FPS inference, while malformed declared resources surface errors. Realtime observation-cache
alignment uses the same timing reference. Synchronization import binds the original selected paths to
the job's staged paths and uses the producer's forward filename function, with no prefix stripping.
Thirty-seven SkellyCam timing/media tests pass. These final shared timing methods must be published
and installed before the full FreeMoCap integration run. Geometry remains untouched. App QA is gated
on that run, including new identical-name variant coverage and the real synchronization/import test.

Pre-geometry cleanup checkpoint: both playback routers use full filename IDs. FreeMoCap's unused
per-video/all-video timestamp routes are removed; SkellyCam's active batch timestamp route uses
declared associations and explicit FPS inference. Heuristic CSV statistics are replaced by a shared
reader of the defined multiframe format. Reverse filename parsing and automatic disk transcoding
are deleted; `VideoFilename` only formats names from capture configuration. Device enumeration rejects
ID collisions before dictionary construction. Annotation output embeds a typed source-video/frame-count
relationship in the container and uses H264 MP4 output; playback reads that relationship rather than
stripping suffixes. Missing declarations leave media usable independently. Partial files are excluded
from inventory. Embedded metadata round-trips through MP4/AVI/MOV/MKV in tests.

Validation: 33 focused SkellyCam tests pass; FreeMoCap TypeScript passes. SkellyCam TypeScript is blocked
by its baseUrl deprecation configuration. FreeMoCap integration awaits the user publishing these shared
SkellyCam changes and updating its Git dependency. Do not start in-app QA or geometry matching yet.
Remaining pre-geometry closure includes synchronization result associations, explicit timing references
when recording folders move/rename, and checking media-variant identity through the bundle consumers.
The final app checklist must exercise raw/annotated switching, regeneration, inferred timing, arbitrary
names, same stems with different extensions, malformed metadata, and independent calibration failure.

Processing fallback checkpoint: the published shared reader passes playback integration. FreeMoCap's
`VideoGroupHelper` no longer imports the filename parser: explicit associations determine source IDs
and order; bare video paths use complete filenames as local labels and preserve supplied order.
Duplicate labels/files fail before readers open. Both factories share reader ownership and cleanup;
the separate metadata dictionary and unused filename-reindex flags are removed. Eleven focused tests
pass, covering real videos, declared identities, collisions, unequal counts and partial playback.
No SkellyCam dependency change is needed for this checkpoint. Recordings without declarations do not
silently recover physical camera IDs from canonical names; geometry assignment remains necessary for
operations needing existing calibration. The remaining work is annotation/timing relationships, older
playback routes and unified geometry binding, including the planned fitness approach.

Next checkpoint: all 21 FreeMoCap import/association tests pass against the published copy helper,
including a real brightness synchronization followed by import. Recording declaration loading now
lives in SkellyCam's `VideoAssociations`; processing delegates to it. `VideoMetadata` no longer has
filename-derived camera/recording identity properties. Playback resolves declared sources through the
shared reader, retains unassociated files with file labels and inferred timing, and reuses its initial
probe instead of opening another reader for each video's timing. Malformed declarations are a separate
bundle resource error, leaving viable media visible. Nineteen SkellyCam tests pass. The changed bundle
tests await publishing the new shared-reader methods and updating FreeMoCap's Git dependency.

Still outstanding: `VideoGroupHelper.from_video_paths` parses names when no declarations exist;
annotation relationships and older timestamp routes still apply filename conventions. Their removal
is required before considering the policy unified. Geometry binding and permutation fitness remain
subsequent work. This checkpoint does not claim they are fixed.

Follow-up: the published SkellyCam association dependency is verified; all six focused FreeMoCap
association tests pass using `uv run --locked --group dev pytest`. Import frame-count inspection now
uses the identity-free SkellyCam probe and exposes no guessed camera ID in its API/UI result.

The next source change adds SkellyCam's `VideoCopyPlan`: validate all sources and destinations before
copying, reject collisions and duplicate inputs, and use exclusive destination creation. FreeMoCap
import and sync staging consume it; import rejects an existing recording directory. Sixteen SkellyCam
association/copy tests pass. FreeMoCap endpoint verification requires publishing this additional
SkellyCam change and updating its Git dependency. Synchronization's name-based result association
still needs replacement with an explicit producer relationship; this change only guards its collisions.

The first bounded change adds SkellyCam's typed `VideoAssociations` and writes the existing `videos`
mapping from capture configuration and resolved capture files. It rejects duplicate file associations,
escaping paths, empty source IDs, ambiguous capture containers and conflicting requested extensions.
FreeMoCap's manifest path consumes that shared validation and fails on malformed/conflicting declared
associations instead of silently falling through. SkellyCam's 11 focused tests pass in its own environment.
FreeMoCap integration tests await the user publishing SkellyCam and updating the Git dependency.

This does **not** complete the global migration. Filename-derived metadata, unassigned imports,
explicit timing/annotation relationships, duplicate playback routes, device collision handling and
unified geometry binding remain outstanding. The next chunk must remove competing identity accessors
and wire explicit associations through those consumers. Do not call the overall policy complete or
start app QA with a FreeMoCap dependency that lacks `VideoAssociations`.

This is a static policy and call-site audit, not a claim that every application branch was exercised.
Before deleting an exposed API, trace its remaining standalone and external-facing consumers. Before
changing source scope, inspect merges of descriptors across groups and results. Before changing device
IDs, establish collision handling at collection construction and the impact on saved configuration.
These checks belong to their bounded implementation chunks; none warrants another generic identity
framework or reopening playback performance work.
