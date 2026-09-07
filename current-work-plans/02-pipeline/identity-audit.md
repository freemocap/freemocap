# Camera and media identity audit

2026-09-07. Static cross-repository audit; no runtime verification or implementation changes.
Reviewed repository history, the media-identity plan, architecture review, recording proposal,
and current producers and consumers. Snapshot: FreeMoCap `4c292aa9`, SkellyCam `4709a0d7`,
SkellyTracker `c29d9ec`, SkellyForge `5fe45aa`.

This audit precedes resuming the Mocap/posthoc request walkthrough. Identity policy crosses capture,
import, calibration, recording publication, playback, and both applications. A request-local fix
cannot establish the required contract.

## Findings

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
