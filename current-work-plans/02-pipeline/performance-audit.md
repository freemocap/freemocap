# Recording graph performance audit — 2026-10-11

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
intervals took 2.53–2.78 s, or roughly 36–40 synchronized frames/s. A separate
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
# Structural review and batch triangulation — 2026-10-11

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

| Recording | Frames × points | Rebuild solver each frame | Reuse solver each frame | 32-frame batches | One recording batch |
| --- | --- | ---: | ---: | ---: | ---: |
| Test | 222 × 133 | 0.514 s | 0.410 s | 0.239 s | 0.239 s |
| Sample | 1108 × 225 | 4.728 s | 3.032 s | 2.265 s | 2.864 s |

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

