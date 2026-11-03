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
An installed, prepared Blender is required; the underlying standard workflow can
prepare its isolated add-on environment. Obtain environment-change authorization
where local policy requires it. `--output-profile numerical` explicitly excludes
Blender and must only be compared with other numerical runs. `--recordings-root`
selects existing raw recordings or their acquisition destination. Every run uses a
new output directory and fresh calibration/processing, even when models are cached.
Downloads, data copying and identity capture are outside worker timing; the wrapper's
elapsed time covers the invoked command, including acquisition if needed.

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
  not live inference FPS**. Detailed stage timings remain in the ordinary report.
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
