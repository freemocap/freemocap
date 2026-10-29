# Tensor contract compliance map

Initial source inspection: 2026-10-28. The tables below preserve the initial
[tensor contract](tensor-contract.md) change map, not historical coding-policy compliance.
The implementation update below supersedes the original findings where stated.
Paths below are repository-relative unless a repository is named explicitly.

## Core implementation update — 2026-10-28

Shared tensor interfaces are implemented and tested. `ObservationArrays` now reads
Tracker coordinate/confidence arrays directly, caches identity selections rather
than mutable values, and supplies recording assembly, publication, provenance,
camera matching and live triangulation. Recording assembly scatters whole arrays
in bounded frame batches. No production core call to `Observation.to_keypoints()`
remains; the standalone detector comparison diagnostic still uses that API.

`ModelRecordingReconstruction` owns immutable `DataTensor` channels rather than
per-frame `SkeletonReconstruction` dictionaries. `RecordingPoseOutputs` consumes
Forge's `HydratedPoseBatch`; recording publication reuses the same channel buffers.
Mapped landmarks, connected landmarks, segment positions, rotations, angles,
residuals and center of mass retain declared identities and presence companions.
Sample positions bind to existing timing at publication; units/reference context
also comes from that existing publisher. No new clock or file format is introduced.

Global 2 is still open: `recording_roll_adapter.py` isolates the conversion required
by Forge's object-only `ContinuousRollResolver.resolve_pose`. Forge also exposes
object-dtype pose-solution metadata to joint calculations. A Forge-owned array API
and corresponding live/core adapters need a separate repository stage. The live
solver still returns numerical dictionaries. Temporal state and dependency order
must stay identical when that interface changes. Other rows below remain work
unless the updated contract explicitly records their completion.
Reconstruction geometry temporaries use bounded chunks; the existing scale-fitting
pass still hydrates the full recording. This stage does not establish a complete
recording memory bound. Core's Forge branch declaration, lockfile, installed package
and clean sibling checkout all matched `development-streaming` at commit
`f5404db5791c69afedf95652ef7cebca316e5ec0` during this read-only preflight.

Validation includes a fresh production numerical-profile run at
`C:/tmp/fmc-g2-1028` (222 frames, three cameras), 131 passing integration/observation
tests including live replay and saved-stage reuse, plus a final 37-test reconstruction
suite covering scalar parity, publication, admission and review consumers. All 38 scientific channels match the prior reference output
within 1e-6 absolute / 1e-8 relative tolerance; human values match exactly and the
largest board difference is 2.28e-13. Identities, timestamps, presence and source
file hashes match. Processing-duration channels are deliberately excluded.

Reference observation assembly (name discovery plus coordinates, all three
cameras with 225 points) measured 238.5 ms before and 18.0 ms after, medians of five
warmed runs. This is a component benchmark, not an end-to-end speedup claim.
Fresh graph processing took 26.27 seconds of worker lifecycle. Evidence is in
`.test-artifacts/tensor-contract/{observation-benchmark,reference-comparison}.json`
and `{global2-processing,global2-tests,global2-reconstruction-tests}.log`.
No GUI or full Blender acceptance ran.

## Existing foundations to retain

| Owner and location | What already fits | Required extension |
| --- | --- | --- |
| Tracker: `core/data_primitives/keypoints.py:Keypoints` | Dense xyz/visibility with a convenience object; basic slices share numeric memory. | Shared prepared name layouts, explicit copy ownership and a batch/frame-view relationship. |
| Tracker: `core/io/prepared_tracker_mapping.py:PreparedTrackerMapping` | Prepared mappings operate over multi-frame arrays; `MappedLandmarkBatch` wraps positions and availability. | Bind stable layouts and retain availability meaning; do not convert mapped results to per-frame dictionaries. |
| Forge: `core/skeleton/pose/hydration_batch.py:HydratedPoseBatch` | Dense origins, orientations, scales and status over frames and segments. | Numeric solution codes replace object-dtype enum arrays; define ownership and composition with temporal state. |
| Core: `core/reconstruction/recording_reconstruction.py:RecordingReconstructionInput` | Recording tensor [F,P,3] and measured-support mask with shape checks. | Shared timeline/layout and explicit ownership; avoid recomputing whole-recording masked copies through repeated `scale_points` access. |
| Core: `core/recording/sample_encoding/channel_series.py:ChannelSeries.batches` | Direct Arrow columns from numeric arrays, bounded rows and frame-aware batches. | Consume the common tensor contract and preserve masks/timing without reconstructing data first. |
| Core: `core/recording/exports/arrays.py:ChannelArrays` | Dense arrays, entry-presence masks and selective/pruned reads; large payloads can be mapped to disk. | Promote common semantics out of export-only code; explicit timeline/layout IDs and owner lifetime. |

## Confirmed representation breaks and proposed replacements

| Location | Observed behavior | Contract-aligned replacement / proof |
| --- | --- | --- |
| Tracker `Observation.to_keypoints` and core `ObservationBuffer.to_keypoints_array` | Repeated stage concatenation followed by per-frame/per-point name routing. | Normalize a known stage layout into an observation tensor once; batch assignments and validity masks; preserve late/missing stages and detector confidence semantics. |
| Core `dataflow/scientific_recording.py:ObservationCollection.accept` | Calls flattening for validation, then deep-copies observations into camera/frame dictionaries. | Explicit owned observation builder and shared normalized measurement tensors; verify producer mutation cannot corrupt retained data. |
| Core `dataflow/scientific_recording.py:CompletedScientificRecording` | Deep-copies the scientific payload and pickles it to hash in-process integrity. | Controlled immutable ownership plus explicit publication identity; retain the existing mutation-detection guarantee until replacement is proven. |
| Core `posthoc_reconstruction.py:reconstruct_skeletons_with_fits` | Batch mapping/hydration -> per-frame landmark dictionaries and per-segment pose objects. | Pass hydrated/mapped measurement tensors through a numeric temporal resolver; compare every output and reset state against the existing implementation. |
| Forge `pose/roll_resolution.py:ContinuousRollResolver` | Numeric orientations are carried in dictionaries of quaternion objects and recursive per-pose dictionaries. | Prepared parent/topology arrays and numeric rolling state; keep chronological and parent-before-child dependencies. Separate Forge repository stage if its interface changes. |
| Core `recording_pose_outputs.py:RecordingPoseOutputs.calculate` | Pose objects -> dense arrays -> batch geometry -> per-frame dictionaries/objects; copies static lengths into each frame. | Accept/return composed tensor batches and shared static fit data; preserve raw mapped observations versus reconstructed landmarks. |
| Core `recording_reconstruction.py:ModelRecordingReconstruction` | Whole recording represented as a tuple of `SkeletonReconstruction` objects. | Recording measurement collection with lightweight on-demand frame views; no duplicated static fit payload. |
| Core `sample_encoding/reconstruction_samples.py:ReconstructionRecording.series` | Allocates each full channel tensor and fills it from per-frame named dictionaries. | Publication binds channel metadata to existing tensor slices or bounded outputs; test absent channels and component ordering. |
| Core `streaming/channel_helpers.py:assemble_channel_bytes` and segment/keypoint producers | Rebuild Float32 rows from per-name dictionaries; lengths are converted to individual small arrays. | Stream frame views using prepared wire layouts and explicit bulk conversion; keep wire protocol compatibility during migration. |
| Core `parquet_storage/parquet_reader.py:read_batches` and `result_processing/saved_reconstruction.py:read_saved_channel` | Filter after reading batches; requested channels/runs can cause repeated full scans. | Shared selective tensor reader retaining one recording dataset and row-group pruning. Numeric assembly already uses Arrow/NumPy and should be retained. |
| Core `result_processing/saved_observations.py:read_saved_observations` | Loaded channel tensors are rebuilt into frame/stage/Keypoints object collections. | Return observation tensors directly to batch consumers; an annotation compatibility adapter must be explicit and bounded. |
| Core `exports/wide_csv.py:_export_scientific` | Global shared timeline required; NumPy exports omit entry presence; current convenience pose export combines positions/rotations. | Versioned strict tensor archive with explicit sample timelines and companion tensors; keep convenience projections explicitly separate. |
| Core `exports/arrays.py:ordered_arrays` | Composite poses concatenate full arrays even when inputs are disk-backed; timelines are assembled in memory. | Bound composite and timeline allocation; strict tensor export need not combine separate runtime buffers. |
| UI `services/recording/playback-parquet.ts:decodePlaybackParquet` | Column chunks -> per-scalar object/Zod validation -> per-frame arrays -> final arrays. | Batch validation and direct typed-array assembly with no scalar object materialization. |
| UI `services/recording/playback-data.ts` and `ThreeJsCanvas.tsx` | Frame copies, repeated layout lookup/reordering and structured cloning into the renderer worker. | Prepared display buffers, shared metadata, frame views and explicit worker buffer ownership. |
| UI face/keypoint/bone/connection/axis renderers | Point dictionaries, CPU matrix/endpoint repacking and repeated metadata lookups. | Stable topology and dense GPU inputs; computation is still necessary, but scalar object reconstruction is not. |

Paths under `core` above are under `freemocap/` in the core repository. Tracker
and Forge paths are under their respective package directories. UI paths are
under `freemocap-ui/src/`. This is a representation audit, not a statement that
each listed site is the dominant measured performance cost.

## Necessary work versus avoidable work

- Temporal roll is path dependent. Its chronological progression and parent
  dependencies must remain. Object construction around each numeric step can go.
- Solver dispatch over segment definitions or visibility groups can be appropriate:
  each dispatch may process many frames through a native numerical kernel.
- Changing precision, reordering noncontiguous axes, decompression, and uploading
  GPU data perform real work. Name the allocation and reuse its result; do not
  promise that all boundaries are zero-copy.
- Synchronization, interpolation, filtering, measured support and solver status
  change or qualify scientific meaning. They must not be hidden in a generic
  array conversion helper.
- Ragged detections and changing layouts must retain identity. Do not impose a
  fixed global person-count axis or drop missing points to simplify packing.
  Start with existing single-instance layouts; new layout epochs or explicit
  indexed batches handle changing populations without per-point dictionaries.
- Compiled metadata maps and authored skeleton dictionaries are not numeric
  contract violations. The violation is using them repeatedly to carry or route
  every individual measurement in normal operation.

## Implementation ownership and review boundary

Core should first define/test the integration contract using existing array
interfaces. Tracker/Forge retain independent numerical types. Any change to a
dependency's public interface gets a separate repository stage, branch preflight,
and human commit/push handoff before core consumes it. Browser buffers mirror the
scientific semantics but need not reproduce Python classes.

The initial contract-definition outcome was a reviewed interface plus this change
map and the acceptance examples in the contract. Current implementation and measured
limits are recorded above; the remaining migration and full-application performance
acceptance are still open. Identifying a site in this audit does not authorize a
blanket rewrite of every dictionary or loop.
