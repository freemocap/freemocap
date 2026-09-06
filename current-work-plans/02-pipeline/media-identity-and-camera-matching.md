# Media identity and camera matching

Status: design proposal, 2026-09-06. Review before implementation, especially the new
camera-assignment search. This document does not authorize implementing that search.

Current scope clarification: mocap accepts synchronized video groups with identical frame counts.
One shared ordinal selects every video; unequal counts fail. Per-file FPS estimates are not compared
and cannot reject a group. Synchronization is assumed upstream. Broad mixed-rate
ingestion and unresolved temporal alignment discussed below are future design considerations,
not permission to loosen current mocap preflight or playback. See the current contract in
[client playback design](client-playback-design.md).

## Objective

Open recordings and external videos without assuming a filename convention, capture system,
stable device index, or known calibration. Resolve media, timing, and geometry as separate
questions. Preserve explicit relationships when writing; validate and repair them when loading.
Recording folder name remains the recording ID. No additional take/session identity hierarchy.

## Audit findings

Paths below are relative to the project workspace and describe the inspected source.

| Area | Evidence and consequence |
| --- | --- |
| Filename guesses | `skellycam/skellycam/core/recorders/videos/parse_video_filename.py`: an unrecognized filename falls through camera-prefix and embedded-number heuristics. The reported annotated filenames all become camera ID `9` from their date. |
| Duplicate identities | `freemocap/freemocap/core/pipeline/posthoc/video_group_helper.py`: `from_video_paths` repairs indexes, then inserts into a dictionary keyed by the unchanged camera ID. Duplicate IDs overwrite videos; index repair cannot fix this. |
| Conflicting identity authorities | That helper's manifest factory keys the group explicitly, but `VideoMetadata.camera_id` and `.camera_index` still parse the path. Group identity and individual-video identity can disagree. |
| Incomplete recording metadata | SkellyCam `recording_info.py` writes camera configurations but does not write the `videos` map expected by FreeMoCap's manifest loader. The loader also treats unreadable metadata as permission to guess filenames. |
| Playback duplication | Both repositories have playback discovery/parsing. FreeMoCap source validation constructs a processing VideoGroup, imposing equal frame counts and invoking camera guessing merely to inspect media. Video routes key files by stem, allowing same-stem extensions to collide. |
| Timing disagreement | SkellyCam `recording_timing_reader.py` validates explicit columns and supports missing-sidecar FPS timing. FreeMoCap's older playback timestamp helper instead matches substrings, guesses a time column, and suppresses parse errors. The current `/media` route reparses camera IDs to locate timing. |
| Derived video relationships | FreeMoCap `video_node.py` and playback reconstruct annotation relationships using `_annotated`. Annotation can also layer over a previous annotated file. A suffix is not an adequate relationship contract. |
| Import and synchronization | `mocap_router.py` repeats index inference, copies by basename, and matches synchronization outputs by stripping `synced_`. Same-name inputs can collide. Equal frame count is reported as synchronization even though it does not establish temporal alignment. |
| Device identity | SkellyCam `detect_cameras_devices.py` derives IDs from a device path or vendor/product/index, truncated to a two-byte hash; its final fallback is the index. These are useful device hints, not guaranteed permanent physical identities. |
| Calibration policies differ | FreeMoCap `calibration_camera_binding.py` supports exact-ID and structured-index binding for live cameras. `triangulator.py` has an exact-ID ordering path. Neither establishes that a camera remained in its calibrated position. |
| Search is unimplemented | No camera-permutation search was found. SkellyTracker's assignment algorithm concerns tracked objects, not assigning videos to calibrated cameras. Projection/triangulation are reusable primitives, not a completed matcher. |

The supplied log includes successful `/media` and raw/annotated frame responses, plus a manifest
404 used to select media-only playback. It does not prove the remaining UI loading failure's cause.
Reproduce the full UI interaction during the first implementation chunk; retain browser errors and
request/canvas state. Repeated recording-list requests also need checking for remount/effect churn.
Do not equate a successful individual route test with working application playback.

## Proposed contracts

Use typed models and enum states, with classmethod construction and serialization at boundaries.
These are proposed responsibilities, not a requirement for one file or wrapper per row.

| Concept | Structure and meaning |
| --- | --- |
| Recording source | Reuse the recording's source identity, scoped to its sensor group. A camera source represents the recorded image stream. Display name and observed device information are descriptive metadata. It does not assert a permanent hardware serial number. |
| Media entry | Recording-relative path, source reference, media role, and probed video properties. Use the full relative path as the locator initially; do not introduce a second UUID for every file. Persisted relationships can be repaired when files move. |
| Timing description | Explicit recorded timing reference, container presentation times when suitable, or inferred FPS plus offset. State the clock relationship and method. Frame number addresses the decoded stream; timestamps align sources. |
| Derived media relationship | Original media reference and explicit frame correspondence. Frame-preserving annotation shares its original timeline. Trimming, resampling, or dropped frames require their actual mapping. |
| Calibration assignment | Source-to-existing-`CameraModel` entry mapping, selected calibration artifact identity, assignment method and supporting evidence. Preserve geometry identity rather than relabeling it as the source. |
| Resolution result | Resolved entries plus typed unresolved/ambiguous/conflicting findings and supported operations. Expected unknowns are states; malformed declared data is a diagnostic, never silently ignored. |

Distinguish capture device index from processing array position and UI display order. Neither
is camera identity. Algorithms receive an explicitly ordered source list beside their arrays.
Do not copy camera geometry into another intermediate model.

Persist capture/source/media/timing metadata in the existing recording metadata contract, extending
it rather than adding a competing top-level manifest. Keep measurements and model outputs out of
`recording_info.json`. Store accepted processing calibration assignments with processing settings
and the canonical result descriptor as appropriate, not as capture metadata. Search residuals and
observations are not recording metadata. Exact serialization changes require review of those
existing models first; do not create parallel authorities in JSON and Parquet.

## Loading and saving

1. Discover and probe every selected file without inventing physical-camera identities. Duplicate
   basenames in different input directories remain distinct inputs. Reject destination collisions
   before copying, and preserve source-to-output associations through conversion.
2. Read declared metadata through explicit format adapters. Validate paths, uniqueness, file
   availability, and media properties. Distinguish absent metadata from a damaged declaration.
3. Reconcile declarations with available files. Exact existing relationships are useful evidence;
   missing files can be relocated by the user. Optional content fingerprints can help verify
   relocation without treating matching size/duration as proof. Avoid mandatory full-video hashing.
4. For external media with no declarations, allocate distinct recording-local sources once and
   preserve them on import. Opening loose files can use an in-memory inventory without writing.
   Filename patterns may supply display hints or explicit import-adapter suggestions, never runtime
   identity. No generic digit scraping or alphabetical calibration assignment.
5. Resolve timing independently. Missing timestamps with usable FPS are normal. Present malformed
   timestamps as repairable diagnostics; an explicit choice to infer timing may replace them, but
   do not silently claim recorded timing. Variable-frame-rate inputs need usable presentation times
   or an explicit conversion/approximation decision. Different rates belong on timestamp timelines.
6. Save declared relationships when capture/import/export completes. Validate and publish metadata
   atomically. Read paths must not create directories. Newly written outputs must reopen through
   the same resolver used for external recordings.

Unknown inter-camera offsets do not stop independent viewing or detection. They do prevent claiming
synchronization. Equal frame counts/FPS are compatibility facts, not evidence of a shared clock.
Keep incremental decoding and bounded frame caches; identity changes do not justify random seeking.

## Calibration assignment workflow

Playback and detection do not require calibration. Single-camera planar reconstruction does not
require triangulation geometry. A downstream operation consuming saved reconstruction should not
reload calibration unnecessarily. Only operations needing unresolved geometry are blocked.

The processing panel offers a camera-assignment view after choosing calibration:

- One row per source: thumbnail, display label, file, timing status, proposed calibration camera,
  and the reason for that proposal. Files and device hints are inspectable without becoming keys.
- Choose assignments manually; prohibit assigning the same calibration camera to two simultaneous
  sources. Unused calibration cameras are allowed. Explicit reliable partial assignments can anchor
  the remaining search, but incomplete geometry must not enter a computation requiring all sources.
- Exact IDs and saved assignments can populate candidates. Index matches alone remain suggestions.
  Changed calibration content or media transforms invalidate the relevant validation evidence.
- “Find camera matches” runs a separate cancellable job. It reports progress, then proposed matches
  with coverage, residuals, alternatives and visual reprojection overlays.
- Initial release requires accepting the search result explicitly. Acceptance records the mapping;
  it does not certify that stale geometry is physically correct. Insufficient or contradictory
  evidence remains visible, with actions to inspect timing, gather observations, or recalibrate.

The API returns the same typed resolution state and operation capabilities used by the UI. Do not
have separate frontend filename inference. Prefer extending existing recording/preflight responses;
final endpoint names and payloads are a review item after the contract is agreed.

## Proposed geometric search — fully new work

Inputs: resolved sources, selected fixed calibration geometry, aligned shared observations, image
coordinate transforms, and any explicitly accepted assignments. Start with identified Charuco
corners; arbitrary human/object detections require reliable cross-view correspondence first.
Do not assume one person or match similarly numbered detections across cameras without evidence.

1. Check overlap, timing evidence, observation coverage, and image compatibility. Scaling/cropping/
   rotation must be represented correctly relative to calibration intrinsics. Unknown incompatible
   transformations produce a diagnostic rather than a compensating camera permutation.
2. Generate injective assignments respecting accepted anchors and demonstrable incompatibilities.
   Device/filename hints rank candidates but must not exclude plausible assignments by themselves.
3. For small rigs, evaluate bounded enumeration with progress/cancellation. Record when a search
   is incomplete; never claim a global best after truncation. Establish a work limit from benchmarks.
4. Reuse fixed-geometry triangulation and projection. Compare robust residuals on common observation
   support, valid triangulation coverage, positive-depth checks, and per-camera/per-frame results.
   Do not allow a candidate to win merely by dropping difficult observations. Do not optimize camera
   geometry during matching; that is the separate calibration task.
5. Validate on additional frames/held-out observations when sufficient cameras and data allow it.
   Report absolute quality and the margin to alternatives. Low error alone cannot prove identity;
   two-camera cases, symmetric scenes and low-motion observations may remain ambiguous.
6. Return supported candidate, ambiguous candidates, insufficient evidence, or incompatible geometry.
   Select thresholds using representative recordings, synthetic known assignments and deliberate
   failures before enabling automatic acceptance. No invented universal pixel threshold in this plan.

Wrong timing, moved cameras and unsuitable geometry cannot generally be repaired by permutation.
Manual assignment remains available without enough observations to run this search, clearly marked
as user-assigned rather than geometrically validated.

## Ownership and implementation order

First complete the [client playback design](client-playback-design.md) review and prototype:
client decoding/caching, deterministic frame selection, and consolidated sidebar requests take
precedence. The following identity and processing work resumes after that playback boundary is sound.

1. **Contain current loading failures.** Reproduce the reported multi-video playback in the app; prevent duplicate
   keys from losing media; decouple media inspection from synchronized processing validation. Capture
   exact UI failures before prescribing fixes. Make expected media-only playback a normal capability.
2. **SkellyCam media contract.** Own probing, source/media metadata, timing resolution and derived
   frame mappings. Remove camera guessing from low-level video metadata. Consolidate discovery used
   by both applications. Preserve existing sequential readers and timing primitives.
3. **FreeMoCap integration.** Capture/import/playback/posthoc consume the shared resolver. Carry
   explicit relationships through synchronization and annotation; remove repeated loaders and
   substring timing readers after replacing their callers. Annotation reads original images.
4. **Shared calibration assignment.** Extend the existing FreeMoCap calibration binding module for
   realtime and posthoc. Geometry ownership stays with the existing calibration/triangulation code.
   SkellyTracker owns detections/correspondence primitives; SkellyForge does not own media discovery.
5. **Assignment UI/API.** Deliver manual matching and actionable unresolved states before search.
6. **Search prototype and evaluation.** Implement only after design review; benchmark known matches,
   ambiguous cases and wrong calibrations before exposing the proposed user-facing job.

Each chunk ends with focused tests and an app check-in. Sibling changes stay in their source repos.
The user commits/pushes and integrates Git dependency revisions. No editable installs, environment
substitutions, site-packages changes, or agent Git mutations.

## Acceptance matrix

- Four annotated files containing dates: four distinct media entries, correct source relationships.
- Arbitrary names, same basename across directories, same stem with different extensions: no loss.
- Missing metadata, moved recording folder, relocated media: inspect/load without invented identity.
- Conflicting metadata, duplicate declarations, partial outputs: actionable diagnostics, unaffected
  media still inspectable; no silent overwrite or fallback to false scientific relationships.
- Recorded timing, missing timing, invalid declared timing, offsets, unequal rates, trimmed outputs:
  correct explicit temporal semantics and deterministic forward/backward frame reads.
- Device reorder/restart, partial ID overlap, extra calibration cameras: independent source identity
  and reviewed injective geometry assignment; array order cannot change physical assignment.
- Known shuffled calibration, wrong calibration, moved rig, sparse corners, symmetric observations,
  and wrong synchronization: correct recovery or explicit uncertainty, never forced “best” matching.
- New recording appears in Playback; all raw/annotated cameras load; absent Parquet/calibration does
  not prevent inspection; failed calibration remains diagnosable from its detected observations.

## Review decisions before implementation

Confirm the minimal metadata extension and source scope; approve manual-first assignment UX and
initial Charuco search scope. Then define API payloads against existing models and a representative
evaluation dataset. Geometric acceptance thresholds and any unattended matching remain deferred.

## Resume checkpoint — 2026-09-06

Client playback is integrated; user confirms synchronized playback and seeking. The server JPEG
route is deleted. Next audit bundle/media discovery and annotated-source resolution, including
filename-derived duplicate identities and repeated probes. Capture the real annotated-file failure
before prescribing a fix. Then agree the minimal SkellyCam media contract and migrate callers.
Camera permutation search remains planned, not implemented or authorized for implementation.

### First discovery cleanup

Playback source validation no longer constructs VideoGroupHelper or assigns camera IDs/indices.
It uses existing VideoHelper metadata, closes each reader, checks equal counts without comparing
FPS, and reports unreadable files/count mismatches explicitly. Annotated/source count validation
now rejects extra frames as well as missing frames. Direct temporary-video verification passes
with filename parsing patched to fail: arbitrary annotated filenames load; corrupt input returns
an explicit 422. A pytest regression is added, but pytest is unavailable in the installed environment.

This is caller cleanup, not the final media contract. VideoHelper still opens a sequential reader
just to inspect metadata; repeated bundle/media probes and filename-based source/timing association
remain. Next: design the minimal identity-free SkellyCam probe contract and explicit derived-media
relationships, then migrate these callers. No dependency-source changes were made.

### SkellyCam probe handoff

SkellyCam now defines VideoFileMetadata and probe_video_files in
skellycam/core/recorders/videos/video_file_metadata.py. The batch probes distinct resolved paths
once, closes captures, and carries no camera ID or index. Reported FPS/frame count are file
properties, not synchronization evidence or a substitute for exact decoded-count validation.
A real 48-frame H264 fixture passes in SkellyCam's own environment. FreeMoCap has not imported this
new API yet: user commit/push and Git dependency integration must precede that migration.

The 15:28 log has one bundle request and no ERROR/WARNING/FAILED entries, but 22 recording-list
requests across the session. Investigate refresh triggers before declaring request consolidation
complete. Video byte-range requests remain a separate optimization.

### Probe integration resumed

Confirmed the Git-installed SkellyCam exposes VideoFileMetadata/probe_video_files. Playback
source validation now uses that batch API, and annotation length inspection uses its metadata
model directly. These paths no longer construct posthoc VideoHelper/sequential readers for
metadata. Remaining: one request-scoped inventory across bundle consumers, raw timing's camera-ID
association, filename-stem collisions, and explicit derived-media relationships. The Charuco
missing-corners text issue is deferred in the client playback plan; playback acceptance is complete
for this tasklet. Camera permutation search remains a separately reviewed future implementation.

### Mocap/posthoc shared probing chunk

The parent initiative is explicitly mocap/posthoc. Calibration/posthoc remains a separate existing
task; calibration/realtime is deferred. VideoHelper.from_video_path now delegates property probing
to the Git-installed SkellyCam VideoFileMetadata instead of duplicating OpenCV capture/probing.
Its processing-range metadata and camera-ID properties remain for the next boundary review; this
change does not claim to resolve identity. Sequential decoding remains in SkellyCam. Fixture
metadata and forward/backward frame reads pass. No dependency changes are required for this chunk.

Next: separate file properties from source assignment in VideoHelper/VideoGroupHelper, tracing
actual callers before changing the models. Resolve explicit group keys versus filename-derived
camera properties without introducing another geometry wrapper or permanent inventory schema.

### Source assignment guard checkpoint

Calibration CameraModel indices now follow the supplied source metadata order instead of reparsing
each filename. VideoMetadata.camera_index is removed. Filename discovery rejects duplicate source
IDs and ambiguous indices before opening readers, rather than reindexing and silently overwriting
entries. Explicit mappings reject the same resolved file assigned to multiple sources.

This is containment, not the final arbitrary-import resolver: filename-derived camera_id/timing
lookup still exists, and automatic unknown-source discovery/manual assignment remains to implement.
Do not call this identity cleanup complete. Existing canonical recordings should remain processable;
ambiguous inputs now fail explicitly and require source mapping. Check a normal calibration followed
by mocap processing and verify all cameras remain represented. No permutation search is implemented.

### Reaffirmed roadmap: calibration assignment by reprojection fitness

The user reaffirmed this planned capability after the source-assignment guard checkpoint. It must
not be dropped in favor of manual matching alone. Evaluate candidate video-source to fixed-camera-
geometry assignments using shared observations and reprojection fitness, with coverage and ambiguity
checks as specified in "Proposed geometric search" above. Reuse existing triangulation/projection;
do not solve or adjust calibration geometry inside the matching job. Filename/device IDs are hints,
not required truth. Manual assignment remains available when evidence cannot distinguish candidates.

Sequence: explicit source identities and bindings, then agree search inputs/scoring/acceptance and
review examples, then implement a cancellable search with diagnostic results. This is entirely new
search code, not an existing feature. The present reminder confirms roadmap priority, not permission
to bypass the agreed design review or silently accept the lowest-error permutation.
