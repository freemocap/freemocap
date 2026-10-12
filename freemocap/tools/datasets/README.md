# Reference dataset processing

Run commands from **the FreeMoCap repository**, `project/repos/freemocap`,
with its environment activated. Without activation, use
`uv run --no-sync poe ...` after setting up that environment.

With the dev dependencies installed, an interactive terminal shows Rich progress
rows for calibration, mocap, and output validation. Frame counts refer to the
current operation; stages without a known total show an activity indicator.
Counted stages also show items per second and seconds per item alongside the bar.
Calibration counts camera frames; tracking counts synchronized frames (one time
step across the cameras). Rates average the count increase over worker-reported
time since the first count report of the current stage, and update with progress
reports. They exclude work before that first report and reset when stages change.
Rates use compact FR/s and s/FR labels in a contrasting cyan field with separators.
FR means camera frames during calibration and synchronized frames during tracking.
The rate field stays blank until it can be calculated, and for stages without counts.
A counted stage leaves one AVG line in the permanent log when it ends, using the
same observed count/time interval. It is aggregate throughput, not per-camera latency.
Timestamped stage starts, stage endings (with their final reported count and
duration), and pipeline completion/failure remain in terminal scrollback above
the live bars. Per-frame updates only update the bars. Pipeline elapsed time is
retained across stage changes. Warnings and errors remain visible. The complete worker
output is still saved in `processing.log`. Redirected output (or environments
without Rich) uses the same milestone history in plain text. These displays also work for calibration-only and saved-stage
runs; they do not change processing or acceptance checks.

Stage headings have separators and show totals rather than a partial count at
the first poll. Ending counts are explicitly labeled as the last progress report:
the polling loop can miss intermediate and final counter updates. Durations are
intervals between worker log timestamps, not precise detector benchmarks.
Per-video summaries report actual frames newly detected versus observations
reused from the recording cache, plus frames read. Cached model weights do not
mean cached image detections. Full dataset runs copy videos and the board
definition into a new attempt; they do not copy the realtime observation cache.

Calibration runs one video worker per camera. The dataset runner uses threads
inside its separate worker process. Each video start reports its filename, PID,
thread identity, tracker class and available observation-cache entries. Each
video summary reports frames read, new tracker calls, cache hits, observations
published, elapsed worker time and average tracker-call time. Per-video times
overlap; adding them is not the whole-run wall time. Tracker-call timing excludes
video decoding, annotation and writing, and is not a pure detector benchmark.

Numeric tables are reserved for measured results. Setup, saving, sampled stage
intervals and failures remain plain log lines, without duplicate statistics boxes.
Video tables show actual counts, cache hits and worker wall time, followed by the
distribution of fresh tracker-call durations in milliseconds. Calibration reports
its scalar reprojection error in pixels and solver wall time; the available scalar
does not support inventing a residual distribution. Triangulation compares cameras
in shared tables: sample counts, then error distributions in the reported units.
Each table has a column guide above it. Distribution columns are N, NaN %, Inf %,
mean, population SD, minimum, P05, median, P95 and maximum.
NaN and infinity percentages use all input samples, before excluding non-finite
values from the distribution. Reprojection input samples are observed 2D points;
missing 3D reconstructions count as NaN errors. An empty input has undefined
percentages, rather than an implied zero missing-data rate.
The Queued column counts results sent to another worker, not saved files.
Messages about completed file writes explicitly say saved to disk.
P05–P95 describes the central 90% of finite samples, not a confidence interval.
Outliers remain in the mean, SD and maximum; scientific notation keeps extreme
values readable. Triangulation diagnostics precede downstream point gates.
Missing distributions show N=0 with unavailable statistics. Failed stages do not
receive fabricated residuals or success results.

Camera statistics are collected into comparison tables at calibration completion,
so concurrent camera workers do not scatter their tables among solver messages.
Partial or late camera results are retained at shutdown. Each table and its notes
are rendered as one Rich group, preventing live refreshes between their pieces.

```powershell
poe process-test-data
poe process-sample-data
poe process-all-data
```

These commands run the standard production pipelines: fresh calibration, RTMPose
tracking, triangulation, trajectory preparation, automatic coordinate alignment,
skeleton reconstruction. Connected optimization is deferred to `development-skelly-fit`; scale fitting
and landmark/segment reconstruction still run. They rerun
processing even if old results exist. `process-all-data` runs **test_data first,
then sample_data**, stopping at the first failure. It does not run pytest.

The datasets show the same event with three cameras: `test_data` has 222 frames at
6 fps, and `sample_data` has 1,108 frames at 30 fps. Test data is for fast checks;
sample data is for full runs. Low-pass filtering remains disabled for test data
and enabled for sample data; both use production gap filling. Standard runs now
require Blender export and saved-scene validation. Videos are acquired from the
existing released archives, not regenerated.

### Output acceptance

The default `standard` profile requires canonical Parquet and a `.blend` produced
through the saved-segment route. Blender is prepared before calibration/tracking;
its window is not opened. After export a fresh Blender process reopens the scene,
checks its embedded Parquet hash, model/run/group identity and timing, then
compares every frame's landmarks and segment poses, including sample validity.
The ready marker records artifact hashes, source identity, validator version,
Blender/add-on build identity and comparison tolerances. Numerical success alone
cannot publish a complete standard result.

```powershell
poe datasets process test_data --blender-path "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
poe datasets process test_data --output-profile numerical
poe datasets validate test_data
poe datasets validate test_data --output-profile numerical
poe datasets export test_data
```

`numerical` is an explicitly partial profile, useful without Blender. Its results
and old numerical-only ready markers cannot pass complete-run acceptance.
`export` upgrades or retries a saved result on a copied candidate without tracking,
calibration or reconstruction. Successful publication retains the previous result
in history; failure preserves it unchanged. This is also the recovery path after
a reconstruction refresh invalidates dependent exports. Original data is never
deleted to upgrade a ready marker. Normal fresh processing can replace a legacy
preparation as well. Tall CSV is disabled in these profiles; its independent
acceptance consumer still verifies explicit CSV exports. Wide CSV, NPY and NPZ
will extend the required-output reports as their writers land.

Gap filling is supplied by the installed SkellyForge package. FreeMoCap persists
its version-4 provenance and still reads version-2/3 reports. Interpolation runs
before smoothing; filled samples never vote as measured evidence for scale or
alignment. Entirely blank frames remain blank and separate visible intervals.

## Choose work explicitly

Successful workflow processing prints and saves a consolidated plain-text report
as `report.txt` in the attempt and accepted candidate directory. It includes
recorded execution settings/identity, worker timing, all available structured
numerical log tables, detailed operation timing rows, calibration and saved
validation fields. Timing rows overlap and are not additive. Missing evidence is
shown as unavailable. Existing live Rich tables remain unchanged.

Read an existing result without processing or changing acceptance markers:

```powershell
poe datasets report test_data
poe datasets report sample_data
```

Historical reports use their recorded log and metadata; this command does not
revalidate files or claim those results satisfy today's acceptance contract.
The consolidated report currently extracts existing diagnostic log records;
it does not create unmeasured timing percentiles or concurrency statistics.

Posthoc execution selection is recorded in workflow requests and worker results.
`--implementation current` is the default for `process` and `process-all`.
`--implementation graph` is reserved for the replacement and currently fails
before acquisition or output creation, including in dry runs. It never silently
falls back to the current pipeline. Realtime execution is unchanged.

Workflow attempts also contain `performance.json` (schema version 1). It records
implementation, operation, worker-lifecycle status and measured elapsed seconds,
including failures, timeouts and interruptions. Successful workflow ready markers
include this report in `result.performance`. This interval includes subprocess
launch, setup, processing, worker validation, log draining and shutdown. It excludes
parent-side input copying, preflight and publication. It is not inference-only or
GPU timing, and `complete` here does not certify output acceptance. Existing output
validators still decide readiness. A hard parent termination may leave a `running`
report with no elapsed duration; that is incomplete evidence, not a successful run.
Paired execution and numerical comparison are not implemented by this first step.

```powershell
poe process-all-data --dry-run
poe process-test-data --calibration existing
poe process-sample-data --calibration "C:\calibrations\my_calibration.toml"
poe datasets status test_data
poe datasets acquire sample_data
poe datasets calibrate test_data
poe datasets process test_data --from triangulation --calibration existing
poe datasets process test_data --from filtering
poe datasets process test_data --from scale_fit
poe datasets process test_data --from reconstruction
poe datasets validate test_data
```

The complete commands are aliases for `poe datasets process test_data`,
`poe datasets process sample_data`, and `poe datasets process-all`.
`--timeout SECONDS` sets the limit for each
pipeline. `--run-id` and `--sensor-group` select saved inputs when restarting;
the default is the selected saved run and its sole eligible sensor group.

Automatic alignment preserves a calibration marked aligned; otherwise it estimates
alignment from the person. `--alignment calibration` preserves the calibration's
frame and `--alignment person` forces a new estimate. A full run or retriangulation
must produce an acceptable alignment outcome before its results become current,
unless preserving calibration was explicitly requested.

`--calibration existing` selects the separately generated dataset calibration,
then the current prepared recording's calibration, then a recording-local source
calibration. The application-wide last calibration is never selected implicitly.
The chosen path is printed before work. Starts after triangulation reuse saved
3D coordinates and their calibration provenance; calibration and alignment
overrides are rejected there. Missing inputs cause an error, not a hidden full run.

Saved-stage processing retains the saved scientific model definitions. To update
tracker mappings or skeleton definitions, use a full run or the existing explicit
reconstruction-refresh helper; merely rerunning the fit is a different operation.

## Files on disk

Default locations:

- Original downloads: `~/freemocap_data/recordings/freemocap_{test,sample}_data/`.
- Prepared results: `~/freemocap_data/testing/prepared/freemocap_{test,sample}_data/current/recordings/`.
- Separate calibration-only results: the dataset's `calibration/current/recordings/`.
- Previous accepted results: the dataset's `history/` directories.
- Working files, requests, and logs: the dataset's `attempts/` directories.

`--recordings-root PATH` and `--prepared-root PATH` override the first two roots.
They must not overlap. Original downloads are never overwritten. Generated results
are local files; these commands do not upload them or change Git state.

New work happens in a separate folder. The workflow checks the results before
replacing `current`, and saves the previous recording under `history`. Failed runs
leave current results intact and keep their log. `ready.json` identifies the saved
results and their hashes, configuration, source identity, and software provenance.
Calibration-only processing does not replace mocap data or claim to recalibrate
previous outputs. `status` reports the calibration hashes separately.

Directory and marker replacement is recoverable, not one atomic filesystem
operation. If interrupted during replacement, readers reject the pending save.
Run `poe datasets recover test_data` (or `sample_data`) to finish a completed save
or restore the previous results. Recovery preserves interrupted output separately.
Do not manually edit `ready.json` to bypass a checksum mismatch.

Old prepared outputs and logs are not automatically pruned. Keep them while
reviewing a change. Consumers should not hold open prepared files during replacement.

## Tests versus processing

The old `freemocap.tests.prepare_recording_dataset` entry point remains compatible:
it reuses existing preparation, and `--fresh` checks a fresh run without replacing
an existing accepted recording. Use the commands above when the intention is to
**save newly processed data**. The old reconstruction-refresh command remains
available for replacing model outputs from saved 3D points.

Focused workflow checks:

```powershell
python -B -m pytest freemocap/tests/test_dataset_workflow.py freemocap/tests/test_recording_preparation.py
```

Acceptance validates recording structure, frame grids, calibration/alignment,
channel grids, finite values and executed-stage provenance. It does not claim
anatomical accuracy. Reconstruction geometry is checked by the reference tests.

New workflow publications also require versioned provenance for every executed
stage and check the filtering settings against the saved processing report.
Historical files remain readable without invented provenance. The
[recording-contract acceptance tests](../../tests/reference_recordings/README.md#recording-contract-and-provenance-acceptance)
consume fresh outputs and exercise numerical replay while preserving upstream data.
These production-generated outputs are the shared acceptance fixtures for future
CSV/NPZ and Blender integration, alongside focused structural and logic tests.

## Tracker adapter parity and timing

Run the full detector/backend matrix using this repository's existing Python
environment and cached reference recordings/models:

```powershell
python -B -m freemocap.tools.datasets.tracker_matrix test_data sample_data --output .test-artifacts/tracker-matrix/new-run
```

The output directory must be new and ignored by Git. The command runs cases
sequentially in isolated subprocesses, retaining each native log, `report.json`,
`report.txt`, and private baseline observation files. The top-level `report.md`
and `matrix.json` summarize all cases, including failures. It does not replace
accepted dataset outputs. Models use their normal cache machinery; populate
required assets before an offline run.

For one case:

```powershell
python -B -m freemocap.tools.datasets.tracker_comparison test_data rtmpose_cuda --output .test-artifacts/tracker-matrix/new-cuda-run
```

Cases are `charuco_cpu`, `mediapipe_cpu`, `rtmpose_cpu`, `rtmpose_cuda`, and
`mediapipe_cuda`. The last is explicitly **unsupported**: the installed MediaPipe
detectors do not request a GPU delegate and expose no CUDA backend. ChArUco uses
CPU. RTMPose checks actual ONNX session provider registration and fails if the
requested provider is not first; this does not profile every kernel's placement.
The matrix tests app-default configurations (RTMW-x-l 256×192 with YOLOX-m;
MediaPipe body/hands/face; the default ChArUco board), not every model variant.

Both paths use the same complete recording and tracker configuration. The baseline
uses the existing inference service with sequential camera reads; the adapter uses
bounded threaded readers. This is **tracking-boundary regression parity**, not
full posthoc pipeline acceptance or scientific accuracy validation. Both paths
receive the recording timeline, measured where available or inferred from video
FPS. Reports identify the timing methods. This intentionally corrects MediaPipe's
processing-wall-time fallback, so it is not an assertion of numerical identity
with that fallback [@skellytrackerBatchSessions2026].

Comparisons include original camera timestamps, frame identity, stage structure,
point names, bounding boxes, keypoints, visibility, and nonfinite masks. Same-backend
absolute tolerance is 1e-6; exact difference counts are also shown. CPU/CUDA
comparisons are separate descriptive reports, not acceptance verdicts. Aggregate
errors contain mixed units and must not be interpreted as pixel accuracy.

Operation timing includes inference, setup, queue wait and camera batch wait.
Wall time also includes unequal diagnostic write/read/compare work and cold/warm
setup effects. Do not derive a speedup claim from these single ordered passes.
Use isolated repeated runs with symmetric diagnostics for performance acceptance.

Focused adapter/report checks use `unittest`:

```powershell
python -B -m unittest freemocap.tests.test_dataflow_contracts freemocap.tests.test_dataflow_video_sources freemocap.tests.test_dataflow_tracker_adapter freemocap.tests.test_inference_service freemocap.tests.test_tracker_comparison freemocap.tests.test_tracker_matrix
```

## Raw triangulation comparison

The experimental backend scientific slice adds real camera matching, per-frame
triangulation and the canonical recording writer. Run it against a complete
recording and an explicit existing calibration, using a fresh ignored directory:

```powershell
python -B -m freemocap.tools.datasets.scientific_comparison RECORDING_DIRECTORY --calibration CALIBRATION.toml --provider cuda --output .test-artifacts/scientific-slice/new-run
```

`report.txt` is the readable summary; `report.json` preserves configuration,
software identity, matching fitness, inference timing and numerical comparisons.
CPU is also accepted. Provider selection here is a request, not independent kernel
placement profiling. This command currently exercises RTMPose only; the broader
detector matrix remains the tracking-boundary test above.

The comparison uses identical observations and geometry for incremental and batch
triangulation, checks missing-value masks, solver contributions and reprojection
diagnostics, then attempts a canonical raw-3D save and exact read-back. It creates
a private recording copy; original recordings remain unchanged. Automatic camera
matching uses the existing recording-wide sampling algorithm. For already resolved
assignment, `process_resolved_scientific_recording` computes each joined frame while
consuming tracking events. Neither route is yet connected to the production API.

Scientific saving requires every declared camera to finish successfully and an
available camera assignment. Matching uses the established posthoc `continue`/`stop`
policy at both computation and saving: a fitness warning does not become an extra
unconfigured stopping rule. The saved tracker metadata retains assignment status,
source-to-calibration mapping and per-camera fitness; continued poor fitness is
never relabeled as verified. Errors use pixels normalized to a 1000-pixel image
diagonal. No matching thresholds are relaxed to make diagnostics pass. Filtering,
alignment, skeleton reconstruction and annotations are not implemented in this slice.


## Complete recording graph experiment

`python -B -m freemocap.tools.datasets.full_recording_comparison RECORDING --calibration CALIBRATION --provider cuda --annotate --output .test-artifacts/full-recording-loop/NEW_RUN`

Use an unused output directory. This command copies videos, recorded timing sidecars,
and calibration into private graph/current recordings. It runs tracking once, then
compares the graph's complete scientific output with the existing scientific task
using those identical observations. `--with-board` adds the explicit ChArUco board
from the calibration; `--detector mediapipe --provider cpu` selects MediaPipe.
CPU/CUDA RTMPose are accepted. The default is RTMPose CPU.

The graph includes filtering, reference alignment, model fitting, reconstruction,
complete observation/spatial checkpoints, final canonical recording, NPZ export,
and optional independent per-camera annotated videos. The reference harness disables
filtering for its 6-FPS recording and enables it above 12 FPS; the resolved configuration
is recorded. It validates saved channel identities, frame/timestamp identities,
missing-value masks, numerical values, camera geometry, reference frames, model
metadata and fitted parameters. Exact byte fingerprints of numerically equivalent
fit inputs are excluded from cross-route equality; actual channel arrays are compared. Each local fit fingerprint is independently checked
against its own saved inputs using the production reconstruction reader.

Inspect `report.txt`, `report.json`, and the executable `graph.json`. JSON includes
per-operation start/finish times, errors and tracebacks. Timings are **not** a speedup
ratio: graph time includes tracking, annotations and exports, while the existing-task
time covers scientific completion only. Scientific tolerance is `atol=1e-6, rtol=1e-8`.
Camera-assignment evidence is saved under the sensor group's processing metadata.
Full-graph reports also include `motion_capture_throughput`: wall seconds divided
by synchronized frame count, and its reciprocal in motion-capture frames/second.
One motion-capture frame includes all camera images at that frame index. This
includes every graph sink (including annotation when requested), but excludes
input-copy setup and the separate comparison harness's validation work. Compare
like configurations and report repeated-run variability separately.

The CLI comparison remains separate from the dataset workflow's implementation
selector. The same graph is now selectable in the application under Mocap processing
settings > Processing stages > Processing pipeline > Experimental typed graph.
It uses existing HTTP start/stop and WebSocket progress. Start at 2D tracking, select
a calibration, and choose an explicit board if ChArUco is enabled. Saved-stage resume,
automatic board discovery and single-camera operation remain unsupported. Optional
application exports use the existing completion handler; Blender launch was not
exercised in application acceptance tests. See the integration status document for
test evidence and limitations.
The graph currently exposes recording-level operations; streaming image loading and
tracking remain inside their bounded adapter, and automatic camera assignment uses
complete recorded observations. See `current-work-plans/02-pipeline/full-recording-loop.md`.


### Serialization performance regression probe

`python -B -m freemocap.tools.datasets.serialization_benchmark RECORDING --output .test-artifacts/performance/NEW_RUN --repeats 3`

This reads an existing reference output's raw 3D channel, then separately times
bounded column construction and scalar versus columnar validation. Repetitions
alternate validator order and require identical coverage, last-sample state and
exact frame/timestamp digests. Input loading is excluded; this is a storage-path
benchmark, not an end-to-end throughput claim. JSON and readable text reports are
written to the new output directory. Complete graph reports also contain actual
per-stage camera-image and object-detector-run counts for checking bounding-box reuse.
See `current-work-plans/02-pipeline/performance-audit.md` for measured causes and limits.

### Concurrency and disk batch experiments

Full-recording comparisons accept `--annotation-workers N` to test annotation
capacity without changing requested outputs. Capacity is recorded in JSON.

`python -B -m freemocap.tools.datasets.concurrency_benchmark SAVED_RECORDING --output .test-artifacts/performance/NEW_CONCURRENCY_RUN --repeats 3`

Compare fitting plus complete-file validation sequentially, with two threads, and
with two fresh spawned processes. Report worker setup and compute times separately;
total time includes startup, independent input reads and shutdown. Exact fitted
numbers and input signatures must match, as must validator state. Declared sets of
segment names are compared without depending on their iteration order. This is not
a persistent-pool benchmark or a change to production worker policy.

`python -B -m freemocap.tools.datasets.storage_batch_benchmark SAVED_RECORDING --output .test-artifacts/performance/NEW_STORAGE_RUN --repeats 3 --construction columns`

Repeat with `--construction rows` and a different output directory. Both paths use
identical frame-aligned batch sizes, validation and the production zstd writer with
fsync and atomic replacement. This isolates Python row-dictionary construction from
NumPy/Arrow column construction; neither path writes individual scalars to disk.
Reports split construction, validation, writer remainder and cached read time across
four batch sizes. Exact values and validation state are checked after readback.
The experiment saves one real raw-3D channel, not a publishable complete recording.
Its Parquet files deliberately remain diagnostic artifacts in the output directory.

## Annotation execution comparisons

The full-recording comparison accepts `--annotation-execution process` (default)
or `--annotation-execution thread` with `--annotate`. Both use the same drawing and
encoding operation. Process workers belong to one recording and shut down after
it finishes; `--annotation-workers` bounds simultaneous camera annotation jobs.

`graph_wall_seconds` includes worker launch and shutdown. The report separately
records `scientific_completion_seconds`, worker readiness waits, per-camera
drawing/encoding timings, and the number of workers still alive after cleanup.
Compare variants sequentially; overlapping benchmark runs compete for resources.

## Isolated component diagnostics

Add `--isolate-components --annotation-execution thread` to the full recording
comparison command to measure the existing graph handlers one at a time. It still
uses the same input bindings, scientific code, complete recording, save operations,
and output-parity checks. Internal camera batching/native-library workers remain
active. This is diagnostic execution, not a production concurrency policy.

`components/components.json` records each handler's wall time and process CPU time;
the normal report includes those values and explicitly labels isolated execution.
CPU time sums threads in this process and excludes GPU/child-process CPU. A serial
scientific-completion timestamp can include earlier annotation jobs, so use the
individual stage rows for this experiment.

For a separate call-profile run, also add `--profile-components`. It writes one
`.prof` and cumulative-time text report per handler under `components/`. Profiler
overhead is included and its scope is the calling thread, not inference/decoder
worker threads. Do not compare profiled wall time directly with the unprofiled
baseline. Use a fresh ignored output directory for every run. See
[current sample measurements](../../../current-work-plans/02-pipeline/component-measurements.md).
