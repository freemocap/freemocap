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
skeleton reconstruction. Optional skeleton fitting is off by default; scale fitting
and landmark/segment reconstruction still run. They rerun
processing even if old results exist. `process-all-data` runs **test_data first,
then sample_data**, stopping at the first failure. It does not run pytest.

The datasets show the same event with three cameras: `test_data` has 222 frames at
6 fps, and `sample_data` has 1,108 frames at 30 fps. Test data is for fast checks;
sample data is for full runs. Low-pass filtering remains disabled for test data
and enabled for sample data; both use production gap filling. Blender export is
disabled. Videos are acquired from the existing released archives, not regenerated.

Gap filling is supplied by the installed SkellyForge package. FreeMoCap persists
its version-4 provenance and still reads version-2/3 reports. Interpolation runs
before smoothing; filled samples never vote as measured evidence for scale or
alignment. Entirely blank frames remain blank and separate visible intervals.

When explicitly enabled with `--skeleton-fit`, skeleton fitting runs independently in each visible interval, retaining original
frame numbers and timestamps. An interval shorter than three frames or without
any root-pose seed is left null and reported in `skipped_intervals`; root seeds
are never borrowed across absence. The fitted source saves every modeled landmark
alongside its segment transforms and lengths. Its `LANDMARKS_3D` channel contains
predictions; the original reconstruction channels remain fitting inputs and are
not overwritten with those predictions. Playback omits wholly absent fitted frames.

## Choose work explicitly

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
poe datasets process test_data --skeleton-fit
poe datasets process test_data --from skeleton_fit --skeleton-fit
poe datasets validate test_data
```

The complete commands are aliases for `poe datasets process test_data`,
`poe datasets process sample_data`, and `poe datasets process-all`.
`--skeleton-fit` opts into the final fit. `--no-skeleton-fit` remains accepted and
explicitly selects the default (off). `--from skeleton_fit` requires `--skeleton-fit`.
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
and fitted channel completeness, finite values, and unit rotations. It does not
claim anatomical accuracy or enforce experimental fit-quality thresholds.

New workflow publications also require versioned provenance for every executed
stage and check the filtering settings against the saved processing report.
Historical files remain readable without invented provenance. The
[recording-contract acceptance tests](../../tests/reference_recordings/README.md#recording-contract-and-provenance-acceptance)
consume fresh outputs and exercise numerical replay while preserving upstream data.
These production-generated outputs are the shared acceptance fixtures for future
CSV/NPZ and Blender integration, alongside focused structural and logic tests.

## Historical integration blocker (2026-09-29; resolved)

Fresh test and sample processing passed on 2026-09-30 with installed Forge
revision `cbae21e`, including fitting and channel validation. The earlier failure
below is retained as history, not a current prerequisite for running the suite.

A fresh `test_data` run completed calibration, tracking, triangulation, person
alignment (`foot_support`), and reconstruction, then failed in SkellyForge
revision `31cdfda4` with `KeyError: pelvis_origin`. Production gap filling now
retains missing observations at the recording's tail. The fitter's position
priors require spine landmarks on every frame; `pelvis_origin` is absent from
the final six frames. Supporting missing position-prior observations needs a
SkellyForge change before the default full run can pass.

The failed attempt retained the previous accepted recording. The runner does
not fill those observations, drop frames, or disable fitting automatically.
At that point, sample-data full processing and real saved-stage restart checks
were pending the dependency fix. At that time fitting was enabled by default;
the explicit `--no-skeleton-fit` option did not demonstrate that the fitting-enabled
workflow passed. Fitting is now opt-in as documented above.
