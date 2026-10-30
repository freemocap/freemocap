# Tensor contract compliance map

Initial source inspection: 2026-10-28. The tables below preserve the initial
[tensor contract](tensor-contract.md) change map, not historical coding-policy compliance.
The implementation update below supersedes the original findings where stated.
Paths below are repository-relative unless a repository is named explicitly.

## Globals 5–7 completion work — 2026-10-30

All six approved completion steps and Globals 1–7 are complete. The final
measurements below supersede intermediate timings; older dated implementation
sections retain historical evidence, not the current checklist state.

Approved completion step 1 is complete. `freemocap-ui/tools/benchmark-playback.mjs`
and `playback-benchmark-scene.tsx` run the actual decoder and Three.js renderers
against the accepted 222-frame reference recording. Reports and first/middle/last
geometry evidence are ignored under `.test-artifacts/playback-completion/`.
Source SHA256 is unchanged: `5dca07371cbd5410031f76283a758e099455b34c74498d47995897e6ffb04bd8`.

One warmup and five samples: manifest construction 118.42 ms, local in-memory
HTTP download 17.40 ms, decoding 1142.50 ms, provider readiness 1318.40 ms,
frame preparation 0.3180 ms/frame, renderer subscriptions 0.0081 ms/frame,
renderer CPU updates 0.0662 ms/frame, WebGL command submission 0.0333 ms/frame.
Retained decoded values occupy 4,722,384 bytes. Post-decode JS heap samples
range from 56,950,749 to 143,794,104 bytes and depend on garbage collection.
These are not peak/RSS measurements or GPU completion times. Readiness includes
worker loading and first frame, but excludes precomputed manifest construction,
camera video readiness, and full application startup. Local HTTP does not model
network/storage throughput or long-recording scaling.

Validation: 8 focused Node tests and 8 headless Edge playback tests passed,
including the actual reference recording. Existing pytest 9.1.1 was confirmed
outside the sandbox; the authorized install check made no package changes.
Full TypeScript checking encountered a concurrent camera-state edit at
`cameras-slice.ts:217` (`cameraGroups` missing from `AppStateMessage`); that work
was left untouched and must be rechecked at integration.

Completion step 2 is validated: the decoder reads disjoint identity and value
column selections, prepares numeric row indices, and scatters into exactly sized
Float64 tensors without scalar sample objects or per-frame numerical arrays.
Nine browser tests pass, including arbitrary 1/5-component layouts, shuffled
rows, null references, independent clocks, malformed samples and the reference.
All 13 reference channel identities, frame axes, timestamps and value-byte hashes
match baseline; all three saved renderer geometry cases match exactly. TypeScript
checking now passes; the unrelated concurrent camera edit was resolved externally.
Decoder median is 255.4 ms versus 1142.5 ms baseline (4.47x for this recording).
Two temporary row-index arrays consume 14,923,728 bytes for 1,865,466 source rows;
retained values remain 4,722,384 bytes. No peak-memory reduction is claimed.

Completion step 3 is validated; Global 5 is complete. Playback prepares declared
renderer layouts and Float32 projections once while retaining original Float64
values. Last-view caches avoid per-recording-sample object collections. Multi-source
raw points reuse a merged buffer and preserve independently starting clocks.
The shared live/playback viewport transport packs current view bytes into pooled
owned transfer buffers, sends layout metadata on changes, and separates delivery
acknowledgement from buffer recycling. Source arrays never detach. Worker-held
live presentation values prevent recycling until replaced, expired or reset.
Session disposal rejects stale delivery, with bounded latest-pending backpressure.
Pool capacity retains its session high-water mark so fewer incoming models cannot
stall new values while older models remain temporarily displayed.

Seventeen focused Node tests, ten headless Edge tests (including a real worker
transfer and actual reference playback), and TypeScript checking pass. All 13
channel fingerprints and three geometry captures remain exactly baseline-equal.
Same-harness frame preparation median: 0.318018 to 0.002703 ms/frame; browser timer
resolution limits interpretation at this scale. Report: `prepared-after.json`
under the ignored playback-completion artifacts. The transport performs one
necessary copy into an owned transfer buffer; it is not zero-copy throughout.

Final step 3 review additionally covered independently arriving model instances:
receipt acknowledgements include actual retained packet count per stream, so
replacement capacity cannot be exhausted by instances arriving one at a time.
Eight transport tests passed after this correction, including nine independently
arriving identities, and the real WebWorker smoke test passed again. TypeScript
checking passed. No renderer geometry was changed during step 3.

Completion step 4 is validated; Global 6 is complete. Keypoints, connections,
rigid-body bones, segment axes and face geometry use prepared typed indices and
reusable numerical attributes. Layout changes resolve identities/styles once;
frame updates write numerical arrays directly. Buffer growth preserves mesh
identity and picking registration. Draw counts cover active slot extents while
allocated capacity remains reusable; historical point identities are bounded.

Three numerical tests, fourteen headless Edge tests and TypeScript checking
passed. The four affected renderer tests passed again after draw-count reduction.
Tests cover reordered channels/instances, same-count definition changes, live
expiry, missing data, WXYZ transforms, actual raycast picking and growth to
1,030 points, 300 bones and 520 face points. All 13 channel fingerprints and full
geometry/color/picking arrays match baseline. Reduced draw counts omit only
previously zero-scaled matrices. Renderer CPU median is 0.02162 ms/frame versus
0.06622 baseline (3.06x); subscription timing falls below timer resolution, not
zero cost. Report: `renderers-after.json`. GPU completion is not measured.
Inspection targets retain existing kind/name semantics; occurrence-specific
inspection UI and trails are not introduced.

Completion step 5 is validated. `playback_manifest` now projects timing/filter
columns, excludes provably irrelevant row groups and groups native clocks using
numeric arrays. It retains original identity order, strict duplicate checks
(including undeclared identities), and the last equal duplicate's signed zero.
Fifteen new regressions cover these cases. The reference replay test now uses
the current production `CaptureGroup` adapter without weakening type checks.

Core validation: 122 Python tests and 21 subtests, 20 headless Edge tests with
the actual reference, 18 Node tests and TypeScript checking passed; no skips.
The real three-camera replay processed all 222 frames and verified worker/shared
memory cleanup. Its 28.17-second test walltime is not a throughput benchmark.
Independent Forge NumPy/recording/ownership tests passed 83 tests and 7 subtests.
The accepted Parquet digest remains unchanged.

Remaining intentional boundaries: scientific Float64 arrays become Float32
presentation arrays once; manifest arrays become tuples/JSON for transport;
saved arrays adapt into Forge runtime tensors; CSV/notebook `SEGMENT_POSES`
projects component channels that NumPy retains separately. Camera annotation
uses existing Tracker observation adapters, with no Tracker source edits.
Live `frame-resolution.ts` still projects packed four-component wire coordinates
into owned xyz arrays and merges detector arrays on message receipt. The new
renderer preparation does not remove these wire-adapter allocations, and the
playback benchmark does not measure network decoding. Numerical indexed loops
also remain for tensor scatter, coordinate projection and GPU attribute writes;
the work removes scalar numerical objects and repeated layout preparation, not
every loop or allocation. The generic sample validator retains its existing
scalar fallback for irregular batches; the columnar publication path remains.
Complete Blender/sample-data acceptance was not run: its required prepared
profile is unavailable. An existing unrelated CSS media-query warning remains;
the browser tests pass. Test-managed processes have exited.

Completion step 6 is complete. Final same-reference measurements use one warmup
and five samples. The ten readiness browser tests passed again. The agent's
benchmark workloads ran sequentially, but the host was not otherwise idle.

| Operation | Baseline | Final median |
| --- | ---: | ---: |
| Manifest construction | 118.423 ms | 28.724 ms |
| Local HTTP download | 17.400 ms | 19.600 ms |
| Parquet decode | 1142.500 ms | 256.300 ms |
| Worker-inclusive playback readiness | 1318.400 ms | 626.300 ms |
| Frame preparation | 0.318018 ms/frame | 0.001351 ms/frame |
| Renderer subscriptions | 0.008108 ms/frame | 0.000450 ms/frame |
| Renderer CPU update | 0.066216 ms/frame | 0.015766 ms/frame |
| WebGL command submission | 0.033333 ms/frame | 0.027928 ms/frame |

Readiness samples range from 444 to 637.8 ms. The same limitations stated above
apply: precomputed manifest, camera video and application startup are excluded;
the rendering component benchmark excludes worker transfer and GPU completion.
Very small frame timings approach browser timer resolution. Local HTTP results
do not establish cold-network, storage-throughput or long-recording performance.

All 13 channel fingerprints and all numerical/color/picking arrays across 15
mesh captures at frames 0, 111 and 221 exactly match baseline. The only geometry
evidence differences are reduced draw counts; every omitted baseline instance
has a zero-scaled linear transform. Reference SHA256 remains unchanged.

NPZ and NPY were measured separately, then each repeated to investigate higher
costs. Each run used one warmup/five same-run replacements and five loads;
both repeats are retained, and final medians below pool ten observations.

| Format | Earlier export | Final export | Earlier load | Final load | Dataset size/count |
| --- | ---: | ---: | ---: | ---: | --- |
| NPZ | 0.796359 s | 1.081862 s | 0.044699 s | 0.053827 s | 3,730,968 bytes / 1 archive |
| NPY | 1.010293 s | 1.558842 s | 0.029457 s | 0.050428 s | 9,236,097 bytes / 65 files |

Both export repetitions were slower than Global 4. NPZ's first-run array assembly
rose from 0.456 to 0.614 s, and writing/verification from 0.218 to 0.299 s. A
between-run CPU observation, after the benchmark process exited, found unrelated
Python processes using 198%, 15%, 15%, 15% and 10% of a core, and Electron processes
using 55% and 25%. This demonstrates concurrent activity but does not quantify
its causal contribution. Completion work made no export-writer changes; these
measurements establish neither an export speedup nor a source-code regression.
The export ranges were 0.874–1.147 s for NPZ and 1.472–1.715 s for NPY.
All 65 dataset members, including `dataset.json`, match byte-for-byte across all
four exports. Counts exclude guides/inventory. NPZ remains default; NPY remains
opt-in under its subfolder, with the same runtime loader.

Current saved-reconstruction component costs, one warmup/five runs per model:

| Component | Standard human | ChArUco board |
| --- | ---: | ---: |
| Saved input read | 0.149874 s | 0.139066 s |
| Scale fit | 0.035921 s | 0.024583 s |
| Reconstruction | 1.156184 s | 0.022235 s |

These use 222 frames, filtered saved input and center-of-mass calculation.
All 180 repeated array comparisons match exactly, including NaNs. Copying,
imports, discovery and correctness comparisons are outside timing; inference,
triangulation, filtering and publication are excluded. Historical processing
measurements are not controlled comparators for this run, so no processing
speedup or full-pipeline throughput claim follows from this table.

Memory tradeoffs: retained decoded scientific values remain 4,722,384 bytes;
decoder row-index scratch uses 14,923,728 bytes. Float32 presentation storage is
additional. Post-decode JS heap samples are 88.83–155.28 MB versus baseline
56.95–143.79 MB, dependent on GC and not peak/RSS measurements. No peak-memory
reduction is claimed. Python traced export/load peaks are approximately
6.92/10.47 MB for NPZ and 6.82/10.09 MB for NPY, excluding untraced native memory.

Final reports and reproducible scripts remain ignored under
`.test-artifacts/playback-completion/`: `final.json`, `final-readiness.json`,
`comparison.json`, `processing-costs.json`, `format-repeat-summary.json`, and
separate first/repeat format reports. All owned processes exited; focused diff
checks passed; no generated artifacts are tracked. Changes remain unstaged and
uncommitted for human review. SkellyTracker and trails remain outside this work.

## Global 4 ownership and scientific dataset scope — 2026-10-30

Global 4 is complete. SkellyForge now owns the reusable
`core/data_tensors` definitions and generic contract tests. FreeMoCap imports
them directly, including `ChannelValues`, `DataTensor`, `SampleTiming`,
`TimeSeries` and `RecordingDataset`; the former Core implementations and five
duplicate contract suites have been removed. Source timing is unchanged.
`SampleTiming`, `sample_timing` and `sample_timings` replace the previous
timeline class/module/attribute names. Existing editable dependencies resolve
the Forge implementation directly, under the owner's explicit authorization
to integrate locally without commit/push pauses for this work.

The public scientific dataset includes values, axes, identities, timing,
quality/evidence companions, units, reference definitions and model definitions.
Solver/hydration execution status and caches are excluded. Existing internal
companions can remain in runtime objects; export selects scientific content.
No Parquet schema or companion-publication changes are part of this step.
NPY/NPZ serialize the selected runtime dataset, not every internal object or an
identical copy of Parquet's representation. Saved Parquet remains a valid input
to the runtime dataset adapter.

The audit found that `ReconstructionRecording.series()` publishes numerical
values, while its `ChannelSeries` writes NaN as null in a complete cell grid.
The shared saved reader's `present` mask identifies stored rows, including null
rows; reconstruction's internal `entry_presence` instead indicates available
output values. These meanings must remain explicit in the export adapter.
`solver_status` is not written by this path and is excluded from the public NumPy
dataset rather than invented on reload. Scale-fit values and measured/voting
support remain in the recording descriptor, along with model definitions.

Tracker's standalone `DataStore` is outside FreeMoCap's current processing
paths. Tracker is unchanged; pipeline composition and cross-package reference
tests remain in Core. Forge's existing pose/joint/scale calculation interfaces
also remain unchanged by the ownership move.

### Completed NumPy export integration and validation

Forge now owns the versioned NPY/NPZ writers and loaders. Core's saved-data
adapter streams one scientific channel at a time to both requested writers;
the optional `runtime_dataset` input bypasses numerical Parquet reads. Tests
verify that source channel arrays are released before the next channel is read.
Both formats restore owned tensor-backed objects without pickle or an open file
lifetime. Scientific definitions, native dtypes, signed zeros, original timing,
presence, supplied validity/confidence and fitting evidence are preserved.
Execution status is excluded rather than fabricated from saved data.

Run selection and overwrite retain their existing meaning. NPY is explicitly
opt-in under the selected run's stable `npy/` directory; it does not create
per-export generation directories. Only unchanged obsolete managed NPY members
are removed through recoverable publication. NPZ writes directly to one archive,
without creating loose NPY files first. Format-specific inventory entries prevent
updating one format from relabeling another format's selection or source.

The UI identifies NPZ as the packaged option and NPY as optional loose arrays,
removes the obsolete file estimate/shared-timestamp description, and changes no
default selections. The updated headless interaction test and TypeScript no-emit
check pass. Guides execute with plain NumPy or Forge's `RecordingDataset`
loader; unchanged autogenerated guides can refresh while user notes and kept
guides remain protected. CSV/notebook projections are tested against native NumPy
channels, including separate origins/rotations and authored visibility labels.
Existing preservation of older unselected CSV files is unchanged; the inventory
identifies current selected tables.

Verification evidence (overlapping suites; counts are not additive):

- Forge generic/pose/NumPy/reference suite: 131 tests and 28 subtests passed.
- Core export/consumer/reference suite: 100 tests and 3 subtests passed.
- Core tensor-consumer/checkpoint/reference-replay suite: 72 tests and 14 subtests passed.
- Strengthened runtime/reference tests: 12 passed, including nonnative float32,
  explicit quality companions, exact definition text and independent clocks.
- After the final I/O reuse changes: 58 Forge format tests and 63 Core
  export/publication tests passed, including corruption and staged-file tampering.
- UI interaction: one headless Edge test passed; TypeScript checking passed.

The I/O changes reuse the open NPY handle for write/readback verification and
reuse an artifact's existing hash when constructing the publication journal.
Publication still independently rereads and verifies pending files before moving
them. No verification or edited-file protections were removed.

### Separate format costs — 2026-10-30

Each format ran alone against an isolated copy of the accepted 222-frame test
recording, selecting all five public scientific products: 11 time series and six
static tensors. One warm-up preceded five measured same-run replacements and
five measured loads. Export includes channel assembly, readback verification,
hashing and publication; source copying is excluded. Loading reconstructs owned
immutable runtime objects, without memory mapping.

| Format | Export median | Load median | Dataset files | Dataset bytes | Export traced peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| NPZ, DEFLATE | 0.796 s | 0.0447 s | 1 archive | 3,730,968 | 6,919,369 bytes |
| NPY, uncompressed | 1.010 s | 0.0295 s | 65 inside `npy/` | 9,236,097 | 6,821,892 bytes |

Counts and sizes exclude the outer inventory and guides. Tracemalloc does not
measure total process RSS or all native allocation. These small-recording
measurements are not a general throughput claim. The earlier 0.881 s baseline
selected both formats and stored less scientific context; it is not a per-format
baseline. The initial expanded combined-format result was 1.366 s before the
final I/O reuse changes, so no overall speedup is claimed from these comparisons.

All 65 NPZ members, including `dataset.json`, matched the corresponding NPY
files byte-for-byte. The accepted reference Parquet hash remained
`5dca07371cbd5410031f76283a758e099455b34c74498d47995897e6ffb04bd8`.
Reports and the reproducible local benchmark are in ignored
`.test-artifacts/global4/{npz-costs.json,npy-costs.json,benchmark_numpy_formats.py}`.
No Tracker edits, dependency installs or Git mutations were performed for Global 4.

### Earlier ownership validation

Ownership integration validation: **86 tests and 14 subtests passed without
skips**, covering dense Core consumers, channel layouts, reconstruction,
selective saved readers/checkpoints, and all three reference tensor consumer,
integration and realtime-replay modules. Evidence is in
`.test-artifacts/global4/ownership-tests.log`. Ruff reports ten unchanged
type-checking-import findings in `message_model.py` and
`joint_angles_producer.py`; reversing only the ownership import changes in
memory produces the same findings. No automatic unsafe lint fixes were applied.
The final focused rerun passed seven tests, including explicit checks that Core
reconstruction returns Forge's exact `DataTensor` and `ChannelValues` classes;
see `.test-artifacts/global4/ownership-import-tests.log`.

## Storage implementation update — 2026-10-29

Follow-up, 2026-10-30: the missing notebook dependencies are resolved. Polars
and Plotly are direct core dependencies; Plotly 6.9.0 is installed and the existing
Polars 2.0.0 is retained. Notebook loading, CSV examples and the timestamp-CSV
helper now use Polars, with dense numerical assembly in NumPy. The dependency
skip was removed: 54 export/Polars tests pass without skips. The notebook loader
matches all 36 reference channels exactly, including values, presence, frame IDs
and timestamps; the source is unchanged. This supersedes the notebook-skip
limitation below, not its historical test count. Evidence is in
`.test-artifacts/polars-migration/`.

Global 3 is implemented and validated in core's working tree on `sfn26`, based
on `34d59075`. Global 2 was committed in that revision. The storage changes
below supersede the earlier saved-reader and checkpoint findings; they have
not been committed or pushed.

- `parquet_storage/selected_batches.py` selects declared channel identities or
  complete run/group contents from one caller-owned `RecordingView`. It prunes
  row groups conservatively, projects columns, and preserves bounded batches.
  Missing statistics cause decoding and filtering, never guessed exclusion.
- `parquet_storage/channel_arrays.py` owns the shared array assembly used by
  exports and saved-stage readers. Generic saved channels retain authored
  components, units, frame IDs, timestamps and row-presence information. Export
  component ordering remains an explicit boundary convention. Strict saved
  reads validate complete declared coverage, duplicates, units and timing.
- `saved_observations.py` returns camera `ObservationSeries` containing declared
  `ChannelArrays` and `TimeSeries`. The graph admits these tensors directly;
  it no longer rebuilds a recording of Tracker observations and replays events
  to recover arrays. Matching uses bounded frame views, triangulation projects
  whole camera/stage arrays, and annotation adapts one frame immediately before
  drawing. The current image-plane adapter selects x/y for Tracker's XYZ schema;
  storage retains every declared component. Existing source timing is unchanged.
- `checkpoint_publication.py` decodes retained data once, including when the
  original base run survives and also supplies a new run. Whole run/group
  selection preserves undeclared channel rows so publication still rejects
  corrupt input. `ReconstructionRecording.series()` already passes existing
  tensor arrays into `ChannelSeries`; new tests verify that ownership and the
  bounded Arrow output without replacing working numerical publication code.

Validation: the combined regression run passed **204 tests and 29 subtests**;
one notebook execution test was skipped because pandas and Plotly are absent.
All **six reference consumer, integration and realtime replay tests** passed.
Production restarts from saved triangulation and reconstruction each reproduced
all **36 scientific channels exactly**, including NaNs, declared identities,
components, units, frame IDs and timestamps. Publishing three retained copies
of the reference run plus one derived run passed writer validation and exact
comparison of **129 channels across four runs**. The accepted source file's
SHA-256 stayed `5dca07371cbd5410031f76283a758e099455b34c74498d47995897e6ffb04bd8`.

Component timings below are medians of three warmed runs on the 222-frame,
three-camera `test_data` reference. Channel timings use 36 independent public
reader calls in both versions. Checkpoint comparison uses three copies of the
real reference run and the exact committed pre-change function. These measure
reader/selection work, not complete processing or GUI performance.

| Operation | Before seconds | After seconds | Before/after |
| --- | ---: | ---: | ---: |
| Read 36 saved channels | 6.612 | 1.395 | 4.74x |
| Load saved camera observations | 0.692 | 0.259 | 2.67x |
| Select retained checkpoint data | 2.648 | 1.385 | 1.91x |

Decoded row groups fell from 1,836 to 102 for the 36 channels, from 204 to 20
for saved observations, and from 612 to 153 for checkpoint retention. Decoded
rows fell from 67,156,776 to 3,730,932; 7,461,864 to 899,544; and 22,385,592 to
5,596,398 respectively. Explicitly sharing a view reads all 36 channels with
one file open. Observation loading changed from five opens to one, and the
checkpoint fixture from eight to one, producing the same 6,953,928 output rows.

Peak traced allocation is a tradeoff: channel reads changed from 5.86 to 6.61 MB,
observation loading from 14.08 to 7.70 MB, and checkpoint selection remained
about 2.80 MB. These are Python/NumPy traced allocations, excluding untraced
Arrow/native allocations; they are not process RSS or total-memory guarantees.
Saved arrays own recording-sized storage; export arrays retain their existing
scratch-backed option. Strict channel assembly uses a projected frame/time pass
followed by value assembly, so selected row groups are decoded twice there.

Evidence is under `.test-artifacts/global3/`: `final-tests.log`,
`final-reference-tests.log`, `{triangulation,reconstruction}-restart-parity.json`,
`checkpoint-reference-parity.json`, `readers-{before,after}.json`,
`checkpoint-comparison.json`, and the reader/checkpoint counting reports.
NumPy export contract alignment, playback delivery, browser rendering and
downstream acceptance remain later global tasks. No GUI or server was started;
viewer trails remain deferred.

## Core implementation update — 2026-10-29

Global 2 implementation and reference-data validation are complete. Forge commit
`0038076` on `sfn26` prepares immutable model geometry and groups compatible
segment calculations across samples and segments. Six alternating reference-data
runs measured single-frame human pose recovery at 1.959 s before and 0.378 s after
for 222 frames, with identical numeric values, missingness and solution codes.
The full chronological human reconstruction checks measured 1.639, 1.665 and
1.823 s, below the previously recorded 2.984 s regression and 2.392 s original
baseline. These are backend component measurements, not GUI frame rates.
The rigid-board hydration comparison was effectively unchanged. Prepared metadata
is reused; returned poses remain independently owned and numerical temporaries
still allocate. Peak traced hydration allocation changed from 139,038 to 146,124
bytes, so this is not a claim of lower peak memory or zero allocation.

Forge validation passed 714 tests with one existing skip, plus three reference
tests. Core passed six reference replay/integration tests and the recording-wide
44-array comparison. Hydration reference comparisons used chunks of 1, 37 and 222
frames. New standalone Forge tests cover signed axes, solver precedence, missing
and degenerate inputs, reordered layouts, chunking and retained-output ownership.
Evidence: `.test-artifacts/live-hydration-reference-replay.log`,
`live-hydration-recording.log`, `live-hydration-core-{1,2,3}.log`, and Forge's
`.test-artifacts/live-hydration-benchmark.json`. The measurements supersede the
live-regression finding recorded below. Viewer history and trails remain deferred.

Forge commit `0ff75ef` on `sfn26` supplies `PoseTensor`, `JointTensor` and
`ScaleTensor`. Core consumes that checkout through its existing editable source.
The core changes described here are working-tree changes based on `dd0187dc`.

Recording reconstruction now calls numerical hydration, roll resolution and
joint calculation directly; `recording_roll_adapter.py` is removed. Live
triangulation, camera filtering, world-point filtering, velocity gating and
reconstruction use dense arrays. `ChannelValues` binds explicit component names
through the shared `TensorLayout`; named access is a view, not numerical storage
in a dictionary. Mapping, geometry, topology and output layouts are prepared once.
Streaming producers pack complete arrays. Joint angles use declared flat slices.
Published reconstruction arrays are immutable. Named residual objects remain
only at the existing diagnostic JSON boundary, and frozen scale fits retain
their existing persisted representation.

Recording scale fitting masks and hydrates bounded frame chunks. It retains
recording-wide scalar scale evidence for the unchanged exact-median calculation;
this is not a constant-memory guarantee for an arbitrarily long recording.
Masked input fingerprints match the prior full-array masking operation.

The isolated reference workflow at `C:/tmp/fmc-g2-cf01255c` passed fresh numerical
processing of 222 frames from three cameras, saved-reconstruction reuse, and
live replay. Six reference consumer/replay tests passed. The saved-stage restart
matched all 36 channels exactly, including missingness, sample identities,
timestamps and scientific metadata. Independent comparisons with the previous
core implementation preserved fitted scales exactly; coordinate differences
were below 8e-13. The accepted original reference file was unchanged.

Component measurements show a tradeoff, not universal acceleration. Human
recording reconstruction over 222 reference frames changed from a three-run
median of 1.064 s to 0.665 s. Chronological human reconstruction changed from
2.392 s to 2.984 s in single-run component checks. Profiling identifies Forge's
single-sample `LandmarkPoseGeometry.recover_tensor` as the largest live cost;
grouping compatible segment solves is a candidate follow-up before claiming a
live speed improvement. On 3,552 repeated reference frames, scale fitting changed
from 0.247 s / 95.5 MB peak traced allocation to 0.343 s / 11.8 MB, with exact fit
and fingerprint parity. These allocation figures exclude the preallocated input
and are not process RSS. GUI performance and Blender acceptance were not tested.

Evidence: `.test-artifacts/global2_core_{baseline,compare}.json`,
`global2_live_{baseline,compare}.json`, `global2_fit_profile.json`,
`global2_saved_comparison.json`, `global2-processing.log`,
`global2-saved-reuse.log` and `global2-reference-replay.log`.
The historical findings below are superseded for these migrated paths; selective
Parquet loading, NumPy/CSV export alignment and browser rendering remain later work.

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

SkellyForge owns reusable tensor types; Core imports them and owns cross-package
adapters and tests. Tracker remains independent and unchanged. For the approved
Global 4 work, the owner authorized integration through existing editable
dependencies without commit/push pauses. This does not authorize Git mutations.
Browser buffers mirror scientific semantics but need not reproduce Python classes.

The initial contract-definition outcome was a reviewed interface plus this change
map and the acceptance examples in the contract. Current implementation and measured
limits are recorded above; the remaining migration and full-application performance
acceptance are still open. Identifying a site in this audit does not authorize a
blanket rewrite of every dictionary or loop.

### Tensor cleanup continuation: WebSocket preparation — 2026-10-30

Step 1 complete. Connection-owned CBOR decoding reuses validated static metadata
and exactly equal numerical bytes; changed payloads retain independent ownership.
Model coordinate views carry declared component strides into direct pooled viewport
transfer. Camera overlays retain typed numerical layers and cache drawing indices.
Published frames remain valid across later messages and connection resets; every
stationary frame still advances live notifications.

Validation: 20 focused Node tests, UI typecheck, and 14 headless Edge playback and
renderer tests passed. All 222 accepted reference frames matched exactly for both
models and merged raw keypoints. Source Parquet SHA256 remained
`5dca07371cbd5410031f76283a758e099455b34c74498d47995897e6ffb04bd8`.
A final layer-kind cache correction passed the overlay tests and typecheck.
The initial sandbox browser attempt failed on Windows temporary-file replacement
and browser launch; the elevated run passed.

Receive preparation: original changing-frame median 0.328162 ms/message, current
0.200520 (39% reduction); repeated-frame median 0.320310 to 0.195676 (39%).
The preserved baseline rerun confirmed changing performance at 0.325584; repeated
baseline timing was noisy (0.392833). This benchmark covers reference-derived 3D
messages, not JPEG decoding or camera drawing. Exact equality scans are O(n),
with early exit on changed bytes; no constant-time or allocation-free claim.
Reproduction artifacts are ignored under `.test-artifacts/tensor-continuation/`.

### Tensor cleanup continuation: fresh observation retention — 2026-10-30

Step 2 complete. `ObservationCollection` retains recording-wide coordinate,
confidence, box, detector and presence arrays through `RecordingObservationSeries`.
Stage layouts are shared metadata; annotation creates an ephemeral Tracker adapter.
Delivery admission validates before counting coverage, and finalization preserves
chronological authored identity order independent of arrival order. The normal
fixed-layout case retains its arrays; differing arrival/layout order needs at most
one final permutation. Fresh/saved publication provenance remains explicit.

Validation: 39 focused tests passed, including the complete 222-frame, three-camera
reference prediction and triangulation comparison. Independent matching,
annotation-worker and delivery checks passed 29 tests plus 19 subtests.
Retained source ownership, nested stages, nonzero Z, missing/empty stages,
reordered layouts, boxes and failed-admission retry are covered.

Retention-only benchmark (666 camera observations, 225 points, warmup plus five
measured runs): admission 0.117405 to 0.021653 seconds; batched array extraction
0.017303 to 0.002617 seconds. Retained traced allocations 10,599,416 to 5,058,572
bytes. These are not inference, triangulation or process-peak memory measurements.
Artifacts: `.test-artifacts/tensor-continuation/observation-retention.json` and
`benchmark-observation-retention.py`. The immutable reference hash is unchanged.

The standalone unknown-length calibration `ObservationBuffer` fallback and
`FrameTriangulation`'s result dictionary remain; neither is the replaced fresh
recording observation-retention path. No Tracker changes were made.

### Tensor cleanup continuation: columnar observation publication — 2026-10-30

Step 3 complete. Timestamp publication uses validated sampling arrays directly;
bounding-box publication selects recording-owned tensors and emits complete-frame
Arrow batches. The standalone Tracker-object adapter also emits column batches.
No per-scalar dictionaries or reconstructed BoundingBox objects occur on the dense
recording publication path. Cached stage traversal preserves duplicate-name
precedence and detector flags. Generic ChannelSeries row bounds are unchanged.

Validation: 28 focused tests passed, plus 50 independent checkpoint, retention and
scientific-product tests. Fresh save, run-zero overwrite and retained publication
each validated 3,774 rows columnarly with scalar fallback patched to fail. Every
value, identity, time and null in all three reference box channels and four timing
channels matched exactly: 8,880 rows across 222 frames. Malformed grids, duplicate
samples, wrong units, infinite values and inconsistent times remain rejected.
Arbitrarily mixed external/partial batches retain the existing strict scalar
fallback; the ordinary channel-aligned recording path does not use it.

Reference encoding-only benchmark: 16.304 to 2.790 ms (82.9% reduction), warmup plus
five measured runs of twenty repetitions. This excludes disk I/O, validation and
inference. Artifacts: `.test-artifacts/tensor-continuation/observation-publication.json`
and `benchmark-observation-publication.py`. Source reference hash remains unchanged.

### Tensor cleanup continuation: batched filtering — 2026-10-30

Step 4 complete. `filter_recording_points` extracts valid interval boundaries with
NumPy, groups identical intervals, interpolates and filters compatible trajectory
arrays together, and caches coefficients by exact grid rate within the operation.
Missingness, timestamp gaps, short-run preservation, ownership and report counts
remain unchanged. No clock quantization or interpolation across missing support.

Validation: 30 focused tests and 17 independent gap-filling/checkpoint tests passed.
Full-rate sample_data has 1,108 frames, 225 points and approximately 30 Hz; default
6 Hz/order-four filtering was valid. Reference comparison had zero absolute value
difference and identical missingness/report counts. Synthetic equivalence uses
1e-10 mm absolute tolerance. The 6-fps test_data was not used with a 6 Hz cutoff.
Sample reference SHA256 remained
`3b1bbd5a845e0f652e3376d8b6fdabb4de0486c050e465259856070d6cd0f226`.

Filter-only median: 309.923 to 94.418 ms (69.5% reduction), warmup plus five runs
of three repetitions. Coefficient designs 599 to 115; filter calls 599 to 140.
Report still counts 599 filtered trajectory runs and 1,073 preserved short runs.
Source and reproduction artifacts remain in ignored tensor-continuation storage.

### Tensor cleanup continuation: viewport inspection identity — 2026-10-30

Step 5 complete. Modeled inspection targets require model and subject instance
identifiers. Prepared renderer picking maps retain complete targets; hover equality
and the worker bridge preserve identity. Inspection resolves the exact occurrence,
shows its subject ID and does not substitute another instance when it disappears.
Segment origins now honor declared source strides, as landmarks already did.
Unassigned raw keypoints retain their existing name identity.

Validation: five Node tests passed, including more than 50,000 exact coordinate
checks across all 222 reference frames. Five renderer browser tests include actual
pointer movement/click/pin over overlapping names in two instances of one model
and a second model. Reordering, disappearance, replacement and instance zero are
covered. Independent full browser playback/renderer integration passed all 15 tests;
UI typecheck passed. Reference hash unchanged. This is a correctness fix; no new
speedup is claimed. Identity objects are prepared on layout changes, not per point
on each numerical frame.

### Tensor cleanup continuation: Forge authoring independence — 2026-10-30

Step 6 complete. Cross-project authoring now runs from Core:
`python -m freemocap.tools.generate_tracker_mapping_ratios <mapping.yaml>`.
It prints proposals and errors without changing Tracker mapping files. Forge's
copy, development dependency and Tracker source override are removed. Its offline
lock refresh removed Tracker plus 17 Tracker-only package records, added none,
and changed no retained third-party records. No installed environment was synced.

Forge guards now cover runtime, tests, scripts, type-only imports, literal dynamic
imports, declarations and lock contents. A subprocess blocks Core, Tracker and
Camera imports while exercising standalone tensors and NPY/NPZ round trips.
Validation: Forge standalone suite 844 passed, one existing skip (no adjacent
rigid-fit pairs in the shipped model); one accepted-reference tensor ownership and
NumPy round-trip test passed. Core authoring tests: five passed, with exact report
parity for actual RTMPose and MediaPipe mappings. Independent Core integration:
20 tests passed, including accepted reference tensor consumers. Offline lock check
and both repository diff checks passed.

All six continuation steps are verified. Both reference Parquet SHA256 values
remain unchanged. Generated artifacts remain ignored; Tracker's pre-existing
untracked research files are untouched. No source files were staged or committed,
no branches changed, and no pushes or environment installs/syncs were performed.
The calibration incremental collector, eager FrameTriangulation result dictionary,
and strict arbitrary mixed-row validation fallback remain as documented above;
this completion does not claim every loop or allocation in the application is gone.
