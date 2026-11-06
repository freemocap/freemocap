# Machine benchmarks

Run the **existing** reference-data workflow and physical-camera suite with a small
reporting wrapper. The wrapper does not implement another pipeline, camera driver,
acceptance policy, or test matrix. Core owns this report because it coordinates the
existing Core/Tracker/Forge processing and Core/SkellyCam API integration harnesses.
SkellyCam remains independently usable and unchanged.

Use the repository's configured Python environment, with this checkout as the current
directory. On macOS/Linux the interpreter is `.venv/bin/python`; on Windows it is
`.venv/Scripts/python.exe`. With a worktree, an existing interpreter can be supplied by
absolute path: Python resolves Core from the current checkout and dependencies through
the configured editable installations. Verify those locations in the resulting
provenance; do not change shared environments or set PYTHONPATH.

```sh
python -B -m freemocap.tools.machine_benchmarks dataset test_data \
  --machine mac-mini-m4-pro-24gb --conditions 'AC power; shared desktop; cached models' \
  --output .test-artifacts/benchmarks/test-01
python -B -m freemocap.tools.machine_benchmarks dataset sample_data \
  --machine mac-mini-m4-pro-24gb --conditions 'AC power; shared desktop; cached models' \
  --output .test-artifacts/benchmarks/sample-01
python -B -m freemocap.tools.machine_benchmarks camera --backend both --suite extended \
  --machine mac-mini-m4-pro-24gb --conditions 'AC power; shared desktop; one USB camera' \
  --output .test-artifacts/benchmarks/cameras-01
python -B -m freemocap.tools.machine_benchmarks archive .test-artifacts/benchmarks/test-01 \
  benchmarks/results/2026-11-03-mac-mini-m4-pro-24gb-test-01
python -B -m freemocap.tools.machine_benchmarks compare benchmarks/results/*.json
```

The default dataset profile is `standard`, including Blender export/validation.
An installed Blender executable is required. The standard workflow automatically
builds the matching add-on package, installs it in its managed Blender profile,
and validates it. An absent add-on before processing is normal first-run state,
not a reason to skip Blender or downgrade the run. Failures in that workflow must
be diagnosed and fixed through the owning implementation. `--output-profile numerical` explicitly excludes
Blender and must only be compared with other numerical runs. `--recordings-root`
selects existing raw recordings or their acquisition destination. Every run uses a
new output directory and fresh calibration/processing, even when models are cached.
Downloads, data copying and identity capture are outside worker timing; the wrapper's
elapsed time covers the invoked command, including acquisition if needed.

On Windows, use a short external temporary output root if the video-path preflight
rejects a workspace path. Standard processing exports and validates Blender in the
worker, then automatically opens the scene at its final location after promotion.
The worker's saved `auto_open_blend_file=false` records this deferred launch; it does
not disable the workflow's automatic opening. GUI launch and final promotion are
included in wrapper elapsed time, outside worker-lifecycle timing. The interactive
Blender process does not inherit the worker's captured standard streams.
The benchmark wrapper additionally passes `--close-blender-after-open`: Blender
asserts that the final scene loaded, runs its GUI event loop for two seconds, then
quits gracefully. The workflow waits up to 60 seconds and records GUI exit evidence;
on failure it cleans up only that launched process and fails the run. Ordinary
dataset/application auto-open does not enable this test teardown policy.

Run workloads sequentially. Acquire datasets/models before measured repetitions;
record cold/cache state in `--conditions`. Prefer at least three fresh process runs
per dataset and compare medians/ranges, keeping each repetition separately. One run
is a measurement, not a stable regression baseline. Leave other users' processes
alone and record background load rather than claiming an idle machine.

## What is retained

Each ignored output directory contains `benchmark.json`, `benchmark.md`, the original
runner log and all ordinary runner artifacts. The JSON schema records:

- Public machine label, OS/architecture, CPU/core counts, RAM, GPU where discoverable,
  available ONNX providers, thread settings, before/after CPU load and available RAM.
  Missing hardware information is null; available providers do not prove GPU use.
- Versions, actual import locations, Git revisions, dirty diff hashes and untracked
  source hashes from the existing provenance collector. CPU ONNX Runtime is included.
- Dataset input hashes, dimensions/counts/FPS, executed settings, actual applied
  provider log summaries, fresh calibration, output profile and saved validation.
- Existing worker-lifecycle seconds, synchronized frames/second and aggregate camera
  images/second. These include calibration/setup/reconstruction/validation and **are
  not live inference FPS**.
- Structured stage measurements in `cases[].timing_reports`: scope, outcome, frame/image
  counts, call counts, total seconds, mean/first/after-first/maximum milliseconds.
  The Markdown report automatically prints every stage, including amortized
  milliseconds per synchronized frame and per camera image, paired with frames/s and images/s. `compare` includes
  stage totals, means, normalized costs and their reciprocal rates alongside overall worker measurements.
- Workflow phase timing for automatic Blender preparation, inference service start,
  fresh calibration, mocap, numerical validation, Blender validation, output
  acceptance and shutdown. The ordinary dataset runner saves `timings.json` beside
  each attempt's `performance.json`, including failed attempts, and retains the
  reports in successful `ready.json` results. These are available without the wrapper.
  The processing logger emits the same measurements as versioned full-precision
  JSON events as well as its human-readable table. Historical logs can be rendered
  from either older table format; their source is labeled `log_table_rounded`.
  A SHA-256 of the source processing log accompanies benchmark stage evidence.
- Each executed camera case, inventory, settings/application evidence, recorded and
  streamed FPS, p99 frame intervals, missing frames, failures and server errors.
  The extended suite currently exercises 720p30 and the existing 480p resolution
  transition, controls, recording and lifecycle cases for available camera subsets.
  The separate Cartesian matrix planner describes possibilities, not executed coverage.

Case success retains the existing test's meaning. For example, a resolution-change
case can pass while measuring less than 30 fps; inspect the FPS and existing
`within_one_percent_of_requested_fps` evidence. A failed recording can still contain
useful measured rates. No unavailable result is converted into zero or a pass.

## Compare and preserve

`compare` groups identical workload contracts, preserves failures, and summarizes
successful observations by machine with n/median/min/max and a raw value ratio to the
first successful machine. A time ratio above 1 means slower; an FPS ratio above 1
means faster. Ratios are descriptive, not a statistically justified regression test.
Software, provider, cache and load differences must be reviewed. A machine label
should stay stable and not contain a username or serial number.

Camera models and IDs are retained as context, not matching requirements. Comparable
one-camera cases on a three-camera machine match one-camera cases on another machine;
three-camera results remain a different workload. Control cases include the total and
targeted camera counts. IDs in metric names are normalized to camera ordinals. An extended suite may exercise multiple physical subsets of the same size;
its n counts observations, not necessarily repeated runs on identical devices.
Selected identities and inventory remain attached to each comparison observation. Hardware
and driver differences are expected; compare known overlapping workloads and keep
unmatched cases visible. No blanket machine pass/fail is inferred from camera count.

After inspecting the records, use `archive` to copy only `benchmark.json` and `benchmark.md` into
`benchmarks/results/<UTC-date>-<machine>-<workload>-<repetition>.{json,md}` and commit them.
The archive command refuses to overwrite records or archive a running benchmark.
These small curated records are intentional repository fixtures. Keep recordings,
images, logs, processed outputs and bulk timing arrays ignored. Home-directory prefixes
are replaced with `<HOME>` in portable records; review free-form notes, errors and any
external paths before publishing. Original evidence remains in the ignored run folder.
Never hand-edit measured values. Corrections should add a clearly explained new record.

Verified hardware inventories can be retained separately in `benchmarks/machines/`.
Restricted system queries may return generic CPU descriptions in individual runs;
the stable machine label links these to the independently captured inventory.

See the [cross-platform audit](COMPATIBILITY-AUDIT-2026-11-03.md) for fixed
Windows assumptions and remaining compatibility work.

## Reading the timing tables

A synchronized frame contains one image from each camera: these reference datasets
have three camera images per frame. An inference batch call processes those three
images. Per-call mean is a measured aggregate over calls; per-image cost divides
total work by total camera images and is **not** single-image latency.

Rows overlap: inference sits inside load/track, which sits inside mocap, which sits
inside the dataset worker. Annotation workers also overlap tracking. Do not add the
rows or interpret their sums as a wall-time budget. Workflow timings omit unmeasured
Python imports and bookkeeping; the outer worker includes process startup and exit.
The first-call and after-first means expose initialization effects, but after-first
does not guarantee steady state. The bounded collector does not retain latency
distributions, so p50/p95/p99 stage latency is unavailable, not zero. Camera p99
intervals are separately measured by the existing hardware suite.

Historical records remain unchanged. Detailed new runs are separate observations,
with their own code provenance and cache/load conditions, not replacements for
previous measurements.

## Human-facing run report

Human-requested runs must produce useful tables directly in chat, during long runs
and again in the final response. Artifact links supplement those tables.

### Reading order

1. **Matched cross-machine result.** Lead with three or four outcome rows:
   inference, processing with outputs, and the complete command. Columns are
   machines, with paired `ms/frame · FPS` in each cell. Identify hardware,
   actual providers, input/frame/camera counts and repetitions beside the table.
   Show differences and say which measured phase explains them. If no compatible
   baseline exists, say so; do not substitute another dataset or timing scope.
2. **Processing costs, grouped by purpose.** Use small tables in pipeline order:
   video/tracking; triangulation/filtering/reconstruction; saving/annotation/export.
   Show seconds and paired ms/frame/FPS for frame-processing stages. Keep model
   startup, calibration, preparation and validation in a separate setup/checks
   table, in seconds. Do not lead with Blender preparation or dump raw metric keys.
   Retain the full raw stage detail in JSON and the technical appendix.
3. **Camera-group health.** Follow SkellyCam's `RecordingTimestampsStats` structure:
   recording context, frame timing, processing breakdown, and quality. Group by
   backend and camera configuration. Show target versus achieved FPS, ms/frame,
   available interval distributions (including p99), synchronization and missing
   frames, then acceptance/failure. Compare matching resolution/FPS/count cases
   across machines while naming different camera hardware. Different suite sizes
   are not equivalent workloads. Include failed measurements, never as passes.
4. **Repeatability and evidence.** Show run count and range alongside medians,
   separating between-run variation from within-run latency distributions. Embed
   a labeled plot for multi-machine or multi-stage results when plotting is
   available; use separate panels for scopes and error bars for observed ranges.
   Persist source JSON, readable comparison, revisions, conditions and failures.

### Measurement rules

- One synchronized frame contains one image per camera. Images/s is a separate
  unit. Compare identical scopes and workloads, including output settings.
- Nested/parallel spans cannot be summed into phase wall times. Label nesting;
  show individually measured stages rather than inventing aggregate durations.
  Percentages require a valid, explicitly stated denominator.
- Startup is a fixed per-run cost, not a camera framerate. Derived processing FPS
  is equivalent throughput, not evidence of live realtime performance.
- Do not fabricate percentiles, zero-fill missing measurements, or treat the
  maximum as p99. Say what was not recorded. Preserve SkellyCam's existing
  median/mean/std/min/max and stage/idle statistics when those artifacts exist.
- Differences between machines are observations, not isolated hardware effects:
  disclose software revisions, devices, sample counts, cache and background load.

The final chat must be understandable without reading progress messages: comparison,
phase breakdown, camera health, failures and evidence links. A flat all-stages
spreadsheet is a technical appendix, not the human-facing result. Documentation
changes do not require repeating expensive hardware or processing tests.

Latest grouped example: [Mac–Windows comparison, November 6](MAC-WINDOWS-2026-11-06.md), with matched scopes, processing phases, camera failures and [source-hashed JSON](comparisons/2026-11-06-mac-vs-windows.json).
