# Recording graph performance audit â€” 2026-10-11

## Findings established by measurement

### Why the columnar fast path was disappearing

`ParquetFile.iter_batches(65536)` merged writer row groups and split frame grids.
The rectangular validator then correctly fell back to scalar validation. On the
9,310,524-row sample output, every row took that fallback. Reading the same file
one row group at a time reduced scalar rows to 2,288,020 and combined read/validate
time from 17.456 to 5.857 s, with identical counts, last samples, timing digests
and pending-quaternion state. The remaining scalar rows were already fragmented
by earlier checkpoint rewrites. Evidence: `validation-batch-layout.json`.

Canonical checkpoint readers, saved-channel readers and reference validation now
preserve row-group boundaries. The 65,536-row bound remains for large externally
created groups. Regression tests verify both bounded reading and zero fallback
for intact writer-produced frame grids. Save logs now report elapsed seconds,
columnar rows and scalar-fallback rows to expose future regressions.

Full sample acceptance after this change passed all 36 channel comparisons:
218.877 s versus 289.674 s in the preceding run (24.4% lower observed wall time),
0.197543 s/mocap frame, 5.062 mocap frames/s. Tracking was essentially unchanged
(61.415 versus 61.314 s); remaining wall time fell from 228.360 to 157.462 s.
This is one before/after pair, not a repeated controlled estimate. Source report:
`.test-artifacts/full-recording-loop/sample-row-groups/report.json`.
The test-data comparison stayed approximately flat, as described below. 83 focused
tests passed after adding batch-path counters and save diagnostics; bibliography
validation passed with 18 references and eight bibliography tests.

### Annotation concurrency and remaining execution limits

Two complete test runs with identical requested outputs passed parity: two annotation
workers took 42.102 s (tracking 8.442 s); one took 43.239 s (tracking 8.904 s).
Reducing annotation capacity is not an established improvement; default stays two.
The new `--annotation-workers` benchmark option records capacity in its report.
Sample draw timings in the preceding run were 118.88/125.30 ms per camera frame
for the first two cameras versus 29.11 ms for the last camera. These overlapping
wall measurements are consistent with contention, not independent CPU-time estimates.

The graph still runs tracking as one recording-sized operation before downstream
scientific operations. Automatic matching and recording-wide fitting constrain
readiness; present execution is not a fully overlapped frame-token graph. Moreover,
already-collected frames are fed through `FrameTriangulation` individually and each
call constructs a triangulation helper. Compare existing batch triangulation against
that path before changing it; no scientific solver change was made in this pass.

A concurrent cProfile experiment was rejected: the runtime raised "Another profiling
tool is already active" and produced unusable overlapping call evidence. Its failed
run is retained at `test-operation-profile/`, excluded from throughput comparisons.
The experimental profiling option was removed; use isolated replays or explicit
phase timing for subsequent attribution.

### Repeated Windows save failure

WinError 1175 reproduced in a standalone 100-replacement probe with no pipeline or
Parquet readers (one failure, followed by successful replacements). Its external
cause is still unidentified. The replacement helper now logs and retries this exact
error up to five times with delays totaling 0.91 s, then fails. Microsoft documents
that this error preserves both original file names; errors 1176/1177 can alter state
and are not retried [@microsoftReplaceFileW]. No delete-then-rename fallback was added.
Tests cover transient success, bounded failure, non-retryable errors and repeated
actual Windows replacement. This is resilience against observed transient behavior,
not a claim that retries identify or eliminate its cause.

### Latest full-pipeline measurements

One motion-capture frame includes all three cameras. Wall time includes tracking,
scientific processing, complete saves, NPZ export and all annotated videos; input
copying and comparison-harness verification are excluded.

| Dataset | Stage | Total s | Seconds/mocap frame | Mocap frames/s |
| --- | --- | ---: | ---: | ---: |
| Test, 222 frames | Initial | 78.902 | 0.355416 | 2.814 |
| Test | Columnar milestone | 63.074 | 0.284115 | 3.520 |
| Test | Current | 41.502 | 0.186944 | 5.349 |
| Sample, 1,108 frames | Initial | 467.664 | 0.422079 | 2.369 |
| Sample | Columnar milestone | 298.289 | 0.269214 | 3.715 |
| Sample | Current | 289.674 | 0.261439 | 3.825 |

Current runs passed 29 and 36 channel comparisons respectively; maximum differences
were 9.09495e-13 and 1.36424e-12. Observed total reductions versus initial runs are
47.4% and 38.1%. These are historical single-run measurements, not controlled
statistical estimates. Tracking varied: test 22.282 -> 21.563 -> 9.093 s, sample
97.828 -> 111.774 -> 61.314 s. Sample remaining wall time increased from 186.516 to
228.360 s at the latest milestone, despite its slightly improved total. Do not
attribute whole-run changes solely to the recent storage optimizations.

Test uses RTMPose CUDA without board tracking/filtering; sample adds ChArUco and
filtering. Calibration hashes match within each dataset. The oldest test report
has different inactive board defaults. A preceding sample attempt failed final
atomic replacement with WinError 1175 after 324.643 s; exclude it from successful
throughput but retain it as unresolved reliability evidence. The unchanged rerun
in a fresh directory passed. No save-retry workaround was introduced.

Reports: `.test-artifacts/full-recording-loop/comparison-current.md` and `.json`;
latest complete runs: `test-current-v2/` and `sample-current-v3/` under that folder.
Future full-recording reports include `motion_capture_throughput` automatically.

The first complete graph had real avoidable overhead. The available evidence does
not support blaming video loading or inference-queue blocking. On the 3 x 1,108
frame run, video-batch waits totaled 0.104 s, inference-queue waits 0.219 s and
tracking calls 92.994 s (body plus board). Annotation and recording publication
ran concurrently with scientific reconstruction, but sharing an interpreter still
allows their Python work to delay it.

### Tracker behavior

The posthoc body tracker configuration equals the realtime default at 30 FPS:
five-second person-redetection interval, bounding-box smoothing/prediction, and the
same disabled fitness checks. InferenceService retains and feeds back camera state.
A complete body-only replay measured 24 person-detector executions across 3,324
camera images (0.72%, eight per camera). Reuse is working. This uses the existing
SkellyTracker batch/session/state mechanisms [@skellytrackerBatchSessions2026].

The first body-only replay took 87.095 s, with mean batch time 73.746 ms. An unchanged
repeat took 31.707 s (34.9 synchronized frames/s, including setup). Later 100-batch
intervals took 2.53â€“2.78 s, or roughly 36â€“40 synchronized frames/s. A separate
180-batch diagnostic inspected both ONNX model sessions: CUDAExecutionProvider
was first, followed by CPUExecutionProvider. This is provider inspection, not
per-kernel device-placement proof. The profiler wrapper's timings are diagnostic,
not the baseline throughput measurement.

Machine/runtime conditions vary materially. A GPU snapshot before the repeat already
showed 42% utilization, with several other graphical applications present. It does
not identify which workload caused any particular slow run. Do not credit the
tracking variation to serialization changes: tracking finishes before the sinks in
this recording-level graph. Record repeated timings and hardware/load context.

### Thread contention

Controlled replay of the smaller recording's fitting and the same saved samples'
validation, excluding input loading:

| Work | Alone / sequential | Concurrent threads |
| --- | ---: | ---: |
| Model fitting | 2.678 s | 6.348 s |
| Scalar validation | 3.394 s | 4.770 s |
| Both complete | 6.072 s | 6.349 s |

Threads did not improve throughput here. Profiling fitting showed millions of
Python calls around mapping and per-segment pose hydration; validation traversed
1,183,926 scalar rows and performed millions of dictionary lookups. The premise
that all expensive operations release the interpreter lock is not valid for these
operations. Separate thread pools enforce admission capacity, not Python isolation.

### Serialization changes implemented

- ChannelSeries now constructs bounded Arrow columns rather than allocating one
  Python dictionary per scalar. The 442,092-row probe fell from 2.213 s to 0.146 s.
- Observation encoding fills bounded numeric frame buffers and uses the same column
  builder. Missing points remain null coordinates with zero visibility; declared
  component order is preserved.
- SampleValidator validates complete rectangular frame grids using column operations,
  retaining scalar fallback for mixed/irregular/partial batches. It preserves exact
  coverage counts and chained frame/timestamp digests, including signed-zero bits.
  Quaternion null/unit-length checks retain scalar accumulation order and tolerance.
- On a real saved sample channel (747,900 scalar rows), median validation fell from
  1.792 s to 0.137 s over three alternating-order repetitions. Complete validator
  states matched. Column construction took 0.070 s in that probe.
- Full graph reports now include top-level stage camera-image and object-detector
  counts, separately from durations. These are actual returned stage flags, not
  estimates inferred from configured redetection intervals.

No numerical reconstruction algorithms, confidence thresholds, frame counts or
scientific acceptance requirements were relaxed.

## Full-loop evidence and limitations

The 3 x 222 frame run passed graph/current numerical comparison after optimization:
full graph 63.074 s versus the previous 78.902 s. Final saving fell from 13.621 s to
4.819 s, spatial saving from 10.854 s to 6.462 s, observation saving from 3.480 s to
2.386 s. Loading/tracking stayed similar (22.282 vs 21.563 s). This is a measured
before/after run, not a controlled statistical estimate of whole-graph speedup.

The longer 3 x 1,108 frame recording, with RTMPose CUDA, ChArUco, filtering and
all three annotated videos, completed graph execution in 298.289 s versus the
earlier 467.664 s (36.2% lower observed wall time). Operation wall times:

| Operation | Before (s) | After (s) |
| --- | ---: | ---: |
| Load and track | 97.828 | 111.774 |
| Save observations | 34.312 | 9.857 |
| Match and triangulate | 60.244 | 27.233 |
| Fit model dimensions | 104.960 | 39.687 |
| Reconstruct skeletons | 78.961 | 74.746 |
| Save spatial checkpoint | 85.696 | 28.811 |
| Save final recording | 90.854 | 23.030 |

These overlapping operation durations must not be summed. Fitting and matching
algorithms were unchanged; reduced competing Python work is consistent with their
improved timings, but machine variability prevents attributing every difference
to this change. Tracking was slower in this run. All three annotated videos
contain 1,108 frames. Evidence: `.test-artifacts/full-recording-loop/sample-columnar/`.
The completed comparison passed all 36 saved channels, with maximum absolute
difference 1.3642420526593924e-12. The existing scientific task took 121.577 s;
its narrower workload remains unsuitable as a whole-graph speedup denominator.

### Execution topology experiment

On the saved 222-frame recording, fitting plus complete-file validation was repeated
three times per topology, rotating order. Median end-to-end time was 8.693 s serial,
8.483 s with two threads, and 10.436 s with two fresh spawned processes. Times include
worker imports, input loading and pool startup/shutdown. Exact fitted numeric values,
input signatures and validator state matched. An initial diagnostic fingerprint
mismatch was traced exclusively to JSON serialization order of two declared
frozensets (measured/voting segment names); the benchmark now sorts those sets only.

This does not justify changing production to fresh processes. A persistent pool or
larger work units could amortize startup differently and require separate measurement.
Evidence and reproducible command: `.test-artifacts/performance/concurrency-final/`
and `freemocap.tools.datasets.concurrency_benchmark`.

The graph's declared capacities are two compute threads, two annotation threads and
one recording-I/O thread. During loading, the adapter adds one reader thread per
camera. These are application capacities, not total OS thread counts: ONNX, OpenCV,
Arrow and numerical libraries can own additional native threads. Increasing the
application counts without measuring native work and contention is not warranted.

76 focused unittest tests passed, including differential scalar/columnar validation,
malformed scientific data, arbitrary chunk boundaries, signed-zero timestamps,
permuted component order and buffer ownership. The existing pytest-based storage
suite is unavailable in this environment; no dependencies were installed.

Local evidence lives in `.test-artifacts/performance/` and
`.test-artifacts/full-recording-loop/test-columnar/`. Scratch profiler scripts are
retained only in the ignored diagnostics folder. The permanent repeatable command is:

```powershell
python -B -m freemocap.tools.datasets.serialization_benchmark RECORDING --output .test-artifacts/performance/NEW_RUN
```

## Next measured changes

### Parquet construction and disk batch experiment

The production writer already consumes Arrow batches with zstd compression; it
does not issue a disk write for each scalar. The avoidable row-wise work was
Python dictionary construction upstream of that writer. A direct disk experiment
uses one real 747,900-value, 1,108-frame raw-3D channel, the production writer
(including fsync and atomic replacement), and identical frame-aligned boundaries
and validation for row-dictionary and column construction.

Three repetitions per size, with column runs both before and after the row runs:

| Requested row bound | Row construction + validated write (s) | Column equivalent, repeat (s) |
| --- | ---: | ---: |
| 16,384 | 3.475 | 0.699 |
| 65,536 | 3.426 | 0.607 |
| 262,144 | 4.034 | 0.596 |
| 1,048,576 | 3.964 | 0.551 |

At 65,536, construction alone was 2.881 s for rows versus 0.055 s for columns;
writer remainder was nearly identical (0.422 vs 0.426 s). The earlier column run
measured 0.727 s total at that bound, illustrating runtime variability while still
showing the large preparation cost. This is about 5.6x lower observed total write
time in the repeat, not a whole-pipeline speedup estimate. Increasing column batch
size gives a much smaller gain and increases peak temporary storage; the default
is unchanged. All values, nulls, complete validation state and timing digests pass
readback checks. Reads are OS-cache-warm and must not be described as cold disk
throughput. Files have equal sizes for each row/column pair.

Evidence: `.test-artifacts/performance/storage-row-batches/`, `storage-batches/`,
and `storage-columns-repeat/`. Reproduce using
`freemocap.tools.datasets.storage_batch_benchmark --construction rows` or `columns`.
These are isolated-channel diagnostics, not complete publishable recordings.

### Saved-channel reads and checkpoint selection follow-up

Two further changes remove scalar Python loops without changing publication policy:

- Saved-channel assembly now maps Arrow name/component indices and scatters numeric
  columns into NumPy in batches. Frame/timestamp bookkeeping remains per distinct
  frame; complete scientific validation still precedes assembly. Three real-file
  reads fell from median 4.598 s to 3.762 s (18.2% lower observed time), with identical
  point-array and timing fingerprints. Evidence: `saved-read-before.json` and
  `saved-read-after.json` under `.test-artifacts/performance/`.
- Checkpoint retention and computed-channel authorization now use Arrow masks for
  whole channel identities rather than expanding each row into Python strings and
  tuples. On 9,310,524 saved rows and six retained observation channel identities,
  three alternating-order comparisons measured median 4.294 s scalar versus 1.864 s
  columnar. Every mask matches exactly. This measures selection only, excluding disk
  reading, rewriting and downstream validation. Evidence: `checkpoint-selection.json`.

Both changes retain bounded batches, null-reference identity, explicit target-run
checks, invalid-data rejection and atomic publication. No checkpoint is omitted.
The focused tests include real synthetic Parquet reads with trajectory-major order,
small row groups, permuted declared axes, NaNs, signed zero, incomplete coverage,
invalid identities and inconsistent timestamps, plus mixed channel-mask identities.

Remaining read cost includes scanning a whole file for one requested channel;
predicate/row-group pruning is a separate candidate. Full-file checkpoint rewrites
also remain. Do not conflate these microbenchmarks with new full-graph wall timings.

### Next experiment priorities

1. Profile drawing and fitting in isolation versus concurrent execution. Test process
   isolation for Python-heavy terminal work against thread execution, including startup
   and serialization cost; do not move image arrays between processes unnecessarily.
2. Reduce repeated canonical-file rewrites without discarding independent durable
   checkpoints or scientific verification. This requires a storage/publication design
   decision, not silently skipping validation on retained rows.
3. Expose finer readiness where camera assignment is already known. Automatic matching,
   full-trajectory filtering and recording-wide fitting currently require complete
   evidence; do not claim frame-level graph overlap where it does not exist.
4. Repeat equivalent-workload complete runs under recorded machine load. A realtime
   stream and a pipeline that fits an entire recording, rewrites checkpoints and encodes
   videos perform different work; 30-FPS tracking alone is not a total-runtime proof.
# Structural review and batch triangulation â€” 2026-10-11

The latest audit found an avoidable recording-to-event-to-recording round trip:
the graph already held complete observations, replayed them into a second
collection, then replayed them again through singleton triangulation. The offline
entry point now accepts the completed collection directly and calls the existing
batch helper once. Scientific camera preconditions, completeness, coordinate
conversion, outlier rejection and diagnostics remain enforced. The separately
supported resolved streaming operation remains unchanged.

## Measurements from this review

Saved real 2D observations and saved camera geometry were used for three rotated
repeats of solver-only experiments. Loading, matching, image analysis, annotation
and serialization are excluded. Medians:

| Recording | Frames Ã— points | Rebuild solver each frame | Reuse solver each frame | 32-frame batches | One recording batch |
| --- | --- | ---: | ---: | ---: | ---: |
| Test | 222 Ã— 133 | 0.514 s | 0.410 s | 0.239 s | 0.239 s |
| Sample | 1108 Ã— 225 | 4.728 s | 3.032 s | 2.265 s | 2.864 s |

The 32-frame sample result is 489 motion-capture frames/s, or 110,049 point
instances/s. Positions, camera weights, reprojection errors and NaN masks passed
comparison; largest position difference across both datasets was 9.53e-13.
This uses the existing NumPy/OpenCV triangulator, not a Numba/JIT solver. It does
not establish end-to-end throughput. Full-batch graph integration uses the existing
recording helper without introducing a second batching implementation; the better
sample chunk result is retained for a later controlled optimization.

| Test recording, 222 synchronized frames | Earlier annotated | New batch, annotated | Before batch fix, no annotation |
| --- | ---: | ---: | ---: |
| Total graph wall time | 42.102 s | 35.361 s | 30.666 s |
| Load + tracking | 8.442 s | 7.427 s | 8.878 s |
| Matching + triangulation + preparation | 5.807 s | 2.720 s | 2.144 s |
| Model fitting | 7.889 s | 8.019 s | 3.886 s |
| Reconstruction | 14.837 s | 11.743 s | 11.328 s |
| Spatial save | 11.983 s | 12.087 s | 16.022 s |
| Final save | 3.068 s | 3.132 s | 2.282 s |

All three runs passed 29 saved-channel comparisons. These are individual runs,
not a randomized paired study; do not attribute every elapsed-time difference to
the one code change. Operations overlap and their durations must not be summed.
The new annotated graph achieved 6.278 mocap frames/s overall, while loading and
tracking alone achieved 29.89. Its matching/triangulation breakdown was assignment
1.301 s, buffers 0.059 s, solver 1.003 s, coordinate conversion 0.003 s, array
preparation 0.185 s, payload snapshot/integrity hashing 0.169 s. Reporting now keeps
these subphases and prints per-operation coverage rates with explicit units.

Evidence (ignored local artifacts):
- `.test-artifacts/performance/triangulation-review.py` and `.json`
- `.test-artifacts/full-recording-loop/test-no-annotation-review/report.json`
- `.test-artifacts/full-recording-loop/test-batch-review/report.json`
- `.test-artifacts/performance/batch-triangulation-tests.log`: 22 tests passed.

## Review findings and remaining work

**Standards:** one possible Duplicated Code / Middle Man finding in the repeated
event conversion, addressed by the direct completed-observation entry point.
No blanket claim is made about the whole development branch.

**Spec:** unnecessary singleton offline triangulation is addressed. A separate
gap remains: failed-camera annotation rejects even its usable prefix and partial
encodes are deleted, rather than preserving explicitly incomplete diagnostics.
Healthy cameras still produce complete annotation videos. Scientific completeness
must never be weakened to solve this diagnostic gap.

Annotation has no outgoing edges. The scheduler waits for FIRST_COMPLETED and
admits ready scientific nodes independently. However all pools share one Python
interpreter; separate pools do not eliminate GIL/CPU contention. The final run
join waits for all requested sinks, which is not a science dependency on annotation.
The next material experiment should isolate actual annotation execution, measuring
science completion separately from all-sink completion, with identical observations.
Recording-wide filtering/model fitting retain genuine whole-recording dependencies;
their frame loops need profiling, not arbitrary parallelization of temporal state.
Checkpoint I/O is off the compute dependency path, but still shares CPU resources
and repeatedly rewrites/validates the canonical file. Both remain targets.

Baseline inspection: no local `main` branch. Cached `origin/main` is `75c8acc2`;
its comparison to HEAD spans 879 files of broader development and pins different
dependency branches. Running that code in the current environment would mix
versions. No checkout, dependencies, Git state or main code was changed. Per the
owner's direction, investigation continued locally without building baseline
infrastructure. The existing scientific-task comparison is not a main benchmark.

# Annotation isolation experiment â€” 2026-10-11

Checkpoint commit: `7e963af5` (typed graph, scientific parity and prior performance
improvements). Subsequent measurements below are exploratory and do not change
the application's worker topology or dependency code.

Replayed all 222 frames of the saved test recording: the same model-fitting input
in the main process, plus two camera annotation workloads either in threads or in
prestarted processes. Each worker loads video pixels locally. The parent loads
compact saved observations once and sends that snapshot during worker startup;
there is no cross-process image transport. Three rotated repetitions per mode:

| Workload | Fitting alone | Fitting with annotation threads | Fitting with annotation processes | All work, threads | All work, processes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Load + draw + pixel digest | 1.859 s | 4.781 s | 2.018 s | 5.189 s | 2.019 s |
| Load + draw + digest + encode | 1.715 s | 4.454 s | 3.687 s | 8.005 s | 5.418 s |

These are medians, not whole-pipeline times. Fitted numerical values and input
fingerprints matched exactly, as did every rendered-pixel digest. Encoded outputs
opened with all 222 frames. Encoded bitstreams were not compared; codec output is
not the scientific parity target. This focused replay restores skeleton points,
not detector boxes, and excludes tracking, third-camera annotation, scientific
saves and reconstruction. It uses the actual annotator and PyAV writer.

Process startup and observation transfer cost 8.23 s in the drawing experiment
and 7.81 s in the encoding experiment, excluded from the warm-work medians above.
For these short recordings, creating cold workers for each run can erase the
steady-state benefit. A production experiment needs explicit worker lifecycle,
startup-inclusive timing and full graph parity before changing defaults.

The drawing result demonstrates substantial shared-interpreter contention:
fitting with threads is 2.57 times its isolated duration. Process isolation largely
removes that penalty for drawing. Encoding still competes for CPU resources across
processes; process isolation alone does not make scientific work immune to sinks.
The installed writer sets libx264 CRF 18 / preset fast and leaves codec thread count
unspecified [@skellycamVideoWriter2026]. An explicit encoder-thread-budget diagnostic
is separate from changing that dependency's public API.

Two setup issues were kept out of the measurements: simultaneous saved-observation
reads use an exclusive, nonwaiting recording lock and failed when launched together;
the retained experiment videos use `synchronized_videos`, whereas the saved reader
constructs the newer `videos/synchronized` path. The diagnostic loads once and
explicitly resolves its known historical fixture directory. Neither observation
establishes a lock wait in the running scientific graph.

Local evidence: `.test-artifacts/performance/annotation-isolation.py`,
`annotation-isolation.json`, `annotation-isolation-encoded.json` and their logs.
No runtime default was changed from these isolated measurements.

One-thread encoder follow-up: three rotated trials completed with exact fit and
pre-encode pixel parity and complete 222-frame videos. Median all-work time was
30.441 s with threads and 30.054 s with processes, so this setting is not a useful
default from this evidence. Importantly, fitting-alone time also varied from
2.833 to 6.532 s in that run (median 2.927 s), versus 1.715 s in the earlier
automatic-encoder experiment. Host conditions were not stable enough to attribute
the entire cross-experiment difference to encoder threads. Retain this as a failed
candidate, not a clean causal speedup/regression estimate. Evidence:
`.test-artifacts/performance/annotation-isolation-encoder-one.json`.

Next implementation target: isolate annotation using the existing managed worker
lifecycle, retaining its terminal-sink contract and per-camera failure ownership.
Measure cold and reused workers, scientific completion and all-sink completion,
including real annotation/encoding and every scientific output. Do not replace the
existing worker registry with the diagnostic ProcessPoolExecutor, silently cap
encoder threads, or send video images through multiprocessing serialization.


## Recording-owned annotation processes (2026-10-11)

The owner selected shutdown after every recording. The experimental runner now
uses managed processes for annotation, retaining thread mode as a comparison.
No workers persist across recordings; the application/realtime route is unchanged.

Fresh test-data pair (222 motion-capture frames, three cameras, CUDA RTMPose):

| Measurement | Threads | Processes |
| --- | ---: | ---: |
| Full graph, including requested sinks and worker lifecycle | 31.681 s | 24.061 s |
| Seconds per motion-capture frame | 0.142708 | 0.108382 |
| Motion-capture frames per second | 7.007 | 9.227 |
| Scientific completion | 30.776 s | 23.697 s |

This single pair reduced full elapsed time by 24.1%; it is not a repeated-trial
confidence estimate. Both runs passed 29 scientific-channel comparisons with
maximum error 0.0. All three corresponding encoded annotation files also had
identical SHA256 hashes. Evidence: `.test-artifacts/full-recording-loop/` directories
`test-thread-control` and `test-managed-annotation`.

The 1,108-frame, three-camera sample with board tracking completed graph execution
in 177.434 s (0.160139 s/motion-capture frame; 6.245 frames/s). Annotation took
22.380-27.032 s per camera, with all 1,108 frames written for each camera and zero
workers alive afterward. Saved scientific parity verification passed all 36 channels with maximum
absolute error 0.0; evidence: `sample-managed-annotation/report.json`. The historical 218.877 s sample run predates the batched triangulation
change, so that comparison cannot isolate annotation process effects.

The next measured target is spatial checkpoint saving: 77.237 s elapsed, alongside
50.489 s reconstruction. These overlap and cannot be summed. Separate validation,
array/table construction, compression and write time before attributing that cost
to disk or changing concurrency. Scientific completion was 176.994 s, so annotation
was not the final sink delaying completion in this run.

Validation: 24 focused worker/graph/science tests passed, including decoded-pixel
parity, failed-job recovery, worker death isolation, recording identity rejection,
cancellation before dispatch and after one encoded frame, and worker cleanup.
The before-dispatch cancellation test exercised managed termination during startup.
Eight bibliography tests passed; 20 registered references validated without errors.
Normal cancellation cleans temporary output; forced process termination cannot
promise execution of Python cleanup and can leave an unpublished partial file.

## Save-path diagnosis and realistic writer baseline (2026-10-11)

The owner clarified that one second was illustrative, not an acceptance threshold.
Removed the scratch timing assertions. Performance judgments must use comparable
workloads and measured throughput, with scientific validity tested independently.

Primary guidance: PyArrow exposes row-group size, dictionary encoding and codecs
[@arrowParquetWriter]. Parquet recommends larger groups for sequential IO, at a
buffering cost; its 512 MB-1 GB example is HDFS-oriented and is not automatically
appropriate for this local recording [@parquetRowGroupGuidance]. Arrow documents
persisted benchmark comparisons [@arrowBenchmarkWorkflow]. No hardware-matched
external throughput result was obtained; the Conbench file-write page was
inaccessible. Use the library directly on our data as the local reference.

Captured the real 1,108-frame sample's spatial-save request after tracking and
alignment, preserving its original observations file for replay. This diagnostic
intentionally stops the capture graph at the save handler and records a failed
run; it is not a production or parity failure. All output is under ignored
`.test-artifacts/performance/spatial-capture/`.

Two confirmed waste patterns were removed: constructing 2D batches that were then
discarded during observation reuse, and comparing every uniform batch against
every candidate channel. Mixed-channel inputs retain the full identity selector.
Regression tests failed before the fix and pass afterward. Validation is retained.

| Exact spatial request | Before | After |
| --- | ---: | ---: |
| Isolated save, profiled | 7.878 s | 4.913 s |
| Save alongside fitting/reconstruction, unprofiled | 48.418 s | 45.659 s |
| Concurrent fitting/reconstruction | 44.021 s | 44.207 s |

These are single pairs, not confidence estimates. Saved Arrow table values match;
parsed metadata also matches (serialized metadata key order differs). The original
77.237 s run had a broader concurrent workload. The pair demonstrates contention
but does not isolate GIL handoff from CPU/memory contention. The major concurrency
problem remains; do not claim it fixed or describe 77 seconds as physical disk IO.

### Library-only reference on the exact spatial output

Installed PyArrow 26.0.0; 6,775,420 scalar rows, 11 columns, 115 row groups;
1,497,107,376 bytes in decoded Arrow batches. Preload excluded from timer. Three
rotated trials per variant, no profiler; time includes writer close and fsync.
Every output is read back and checked for table and schema equality outside the
timed region. Memory preloading is a diagnostic control, not a production policy.

| Writer settings | Median seconds (range) | Million rows/s | Decoded Arrow MB/s | File MB |
| --- | ---: | ---: | ---: | ---: |
| Current: ZSTD, dictionaries on all columns | 2.476 (2.464-2.500) | 2.736 | 604.5 | 21.66 |
| ZSTD, dictionary disabled only for value column | 2.301 (2.296-2.379) | 2.944 | 650.6 | 17.39 |
| Snappy, dictionaries on all columns | 2.401 (2.391-2.415) | 2.821 | 623.4 | 23.82 |

MB here means decimal million bytes. Decoded Arrow bytes, encoded Parquet bytes
before compression and actual file bytes are different denominators; never label
the 605 MB/s figure as physical disk throughput. The earlier full-recording replay
included skeleton channels and produced a 39 MB file; this spatial-only writer
comparison produces 21.66 MB with current settings. This is not an apples-to-apples
comparison with published synthetic codec or integer-only benchmarks.

No codec or row-group default changed. A larger row group must also be measured
against our reader/validator, which presently benefits from complete-frame,
single-channel batches. Next experiment should isolate save/reconstruction
contention and preserve bounded memory, rather than selecting compression from a
small writer-only gain. Evidence scripts: `save-profile.py`, `capture-spatial.py`,
`replay-spatial.py`, `spatial-contention.py`, `benchmark-spatial-writer.py`.

Validation: 24 supported focused tests and 8 bibliography tests passed; 23 sources
validated. Two additional pytest-based suites could not import because pytest is
not installed; no dependency installation was performed. New changes remain
unstaged, and generated outputs are ignored.

## Channel storage and worker inventory (2026-10-11)

The graph declares at most five handler threads: compute 2, annotation 2, recording IO 1. The loading stage additionally owns three video-reader threads for this sample and one inference-service thread, closed before downstream recording operations. Annotation uses two managed processes in process mode. Native library threads are additional; configured handler counts are not total OS thread counts.

The controlled contention experiment uses only two Python task threads. It does not involve camera loading, tracking, annotation, WebSocket clients or a graph readiness wait.

| Channel | Spatial compressed MB | Spatial payload share | Final payload share |
| --- | ---: | ---: | ---: |
| OVERLAY_2D | 6.155 | 29.40% | 16.03% |
| BOXES_2D | 0.148 | 0.71% | 0.38% |
| TIMESTAMPS | 0.044 | 0.21% | 0.11% |
| REPROJECTION_ERROR | 4.553 | 21.75% | 11.85% |
| RECONSTRUCTION_COVERAGE | 0.227 | 1.08% | 0.59% |
| TRIANGULATION_WEIGHTS | 0.273 | 1.31% | 0.71% |
| RIGID_BODY_RESIDUALS | — | — | 2.31% |
| MAPPED_KEYPOINTS_3D | — | — | 9.02% |
| LANDMARKS_3D | — | — | 11.45% |
| SEGMENT_ORIGINS | — | — | 4.75% |
| ROTATIONS_WORLD | — | — | 6.61% |
| ROTATIONS_LOCAL | — | — | 6.36% |
| JOINT_ANGLES | — | — | 4.82% |
| DERIVED_POINTS | — | — | 0.17% |
| RAW_KEYPOINTS_3D | 4.691 | 22.41% | 12.22% |
| KEYPOINTS_3D | 4.841 | 23.13% | 12.60% |

Shares sum compressed column-chunk payload, excluding file footer metadata. Spatial file: 21.657 MB, payload 20.931 MB. Final file: 39.346 MB, payload 38.405 MB. Results are for the sample recording, not a universal channel distribution.

The spatial Arrow batches occupy 1,497,107,376 bytes. The value column is 55,050,360 bytes; repeated strings and row identifiers dominate decoded size. On disk, value-column chunks occupy 19,962,314 of 20,931,000 payload bytes (95.4%). Thus repeated labels have small compressed size but large decoded memory/processing footprint. Investigate dictionary-preserving or numeric-array representations before deleting scientific outputs. Raw/filtered coordinates, reprojection errors and camera observations serve distinct reproducibility or diagnostic purposes.

Detailed evidence: `.test-artifacts/performance/spatial-capture/channel-storage.json`. No channels or saved scientific precision were removed. A process-isolation diagnostic uses a single warmed spawn worker; startup and shutdown are timed separately and total work time includes request transfer. Its results are in `process-comparison.json`. This is a diagnostic ProcessPoolExecutor, not a second production worker-lifecycle system.

Process diagnostic result (one fresh pair; sample human-model reconstruction):

| Mode | Save handler | Reconstruction | Both jobs, including dispatch/transfer | Startup | Shutdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Two task threads, same process | 66.068 s | 83.705 s | 83.756 s | 0 | 0 |
| Reconstruction thread + separate save process | 6.784 s | 89.351 s | 89.416 s | 3.521 s | 0.322 s |

Tables and parsed recording metadata match in both modes. The process request
includes the captured approximately 60 MB serialized request, not images. The
handler timer starts inside the child after deserialization; dispatch/transfer
is included in both-jobs wall time but is not separately isolated here. Cold
process total is approximately 93.26 s, so this pair does not show an overall
throughput win. Earlier thread runs were faster, underscoring host/trial variability.
The replay reconstructs the human model, not the additional board model from the
full pipeline; do not call it a complete pipeline benchmark.

Peak sampled OS thread counts were parent 67 in thread mode; parent 80 and worker
65 in process mode. These count existing/idle native-library threads as well as
Python threads, not runnable CPU demand. Process isolation sharply reduced save
latency but does not isolate the GIL as the sole cause. Repeated rotated comparisons
and native thread budgets are needed before promoting a production concurrency
change. Durable pooled workers could amortize startup; that does not remove
serialization or shared CPU/memory costs. Existing annotation lifetime remains
recording-owned; no production process-lifetime policy changed in this diagnostic.

## Independent component baseline

The completed sample-data measurement and profiling pass is recorded in
[Isolated component measurements](component-measurements.md). It includes every
graph handler, wall/process CPU times, historical concurrent comparisons,
three-trial video reading, annotation substeps, downstream call profiles and
explicit profiling limitations. All 36 saved scientific channels matched exactly.
Use `--isolate-components --annotation-execution thread` with the existing comparison
CLI to repeat it; `--profile-components` is a separate, overhead-bearing diagnostic.

## Vector rotation experiment â€” 2026-10-11

[Controlled scalar and batched rotation measurements](vector-math-measurements.md)
identify a concrete arithmetic hot path: a diagnostic scalar replacement reduced
sample human reconstruction from a median 30.600 s to 20.992 s, with maximum
absolute returned-field difference 2.274e-13. Independent paired NumPy batching
has larger microbenchmark gains, but has not been integrated into reconstruction.
No dependency source or production math was changed.

## Simple math vectorization audit â€” 2026-10-12

[Inventory and before/after seconds](math-loop-audit.md): implemented batched
point-validity checks in core (0.5204 to 0.0386 s per sample-recording pass).
Isolated SkellyForge experiment batches attachment and landmark rotations,
reducing human reconstruction from 30.757 to 25.077 s after the core change;
all 1,839,480 numeric outputs match exactly. Dependency implementation awaits
its separate repository stage. No GPU batching work was included.
