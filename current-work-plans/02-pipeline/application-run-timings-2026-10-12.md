# Application run timings and reconstruction audit - 2026-10-12

Both requested graph runs completed. The latest sample run is the one shown in the
user's screenshot, task `20c48cd6-0bb7-4f86-9255-38a76f560729`. The test run is
`8e636ff1-2760-4949-b8a3-db7fe052d98f`. A separate 12.162-second cancelled run of
the current pipeline is excluded from this comparison.

Source: `C:/Users/jonma/skellylogs_data/logs/log_2026-10-12T12_31_42ms243_gmt-4.log`,
performance summaries at lines 644 and 1380. Test completed at 12:38:04; sample at
12:44:53, America/New_York. Extracted numeric evidence is retained locally in
`.test-artifacts/latest-app-runs.json`.

## Actual application measurements

One motion-capture frame contains all three camera views. Test has 222 motion
frames / 666 camera images; sample has 1,108 motion frames / 3,324 camera images.

| Work | Test seconds | Sample seconds |
| --- | ---: | ---: |
| Entire run, including requested exports | **62.919** | **224.391** |
| Read videos and detect points | 16.189 | 70.265 |
| Match cameras and triangulate | 4.255 | 16.894 |
| Fill gaps and smooth trajectories | 0.107 | 0.188 |
| Orient the recording | 1.223 | 5.389 |
| Prepare reconstruction input | 0.008 | 0.021 |
| Fit skeleton dimensions | 5.813 | 25.935 |
| Calculate skeleton positions and joint rotations | **13.641** | **63.211** |
| Prepare detected points for saving | 1.514 | 1.068 |
| Save detected points | 2.999 | 11.530 |
| Prepare 3D points for saving | 0.010 | 0.010 |
| Save 3D points | 4.625 | 16.850 |
| Save final reconstructed recording | 2.679 | 11.516 |
| Annotate video 1 | 6.803 | 30.383 |
| Annotate video 2 | 7.252 | 30.613 |
| Annotate video 3 | 6.176 | 28.065 |
| Scientific exports | 4.515 | 15.399 |
| Blender preparation and exports | 18.173 | 29.547 |
| Concurrent export interval | 18.176 | 29.551 |

Rows overlap and must not be added. Export overlap is working: the elapsed export
interval is approximately the slower Blender branch, not the sum of both branches.
Columnar Parquet validation reports zero scalar fallback rows in both runs.

| Normalized measurement | Test | Sample |
| --- | ---: | ---: |
| Entire run per motion-capture frame | 283.4 ms | 202.5 ms |
| Skeleton reconstruction per motion-capture frame | 61.4 ms | 57.0 ms |
| Dimension fitting per motion-capture frame | 26.2 ms | 23.4 ms |

The reconstruction cost is substantial in both recordings. Whole-run cost per frame
also contains fixed setup/export costs: Blender alone contributes about 81.9 ms per
test frame versus 26.7 ms per sample frame. Different whole-run averages do not by
themselves indicate a synchronization or batching error.

## What is and is not integrated

The export batching/vectorization and concurrent Blender execution are installed.
The prior core `_finite_frame_points` array validity check is installed. The earlier
SkellyForge joint-attachment/landmark batching and specialized scalar quaternion
rotation were diagnostic experiments, not completed upstream changes. See the
existing [math-loop audit](math-loop-audit.md) and
[vector-math measurements](vector-math-measurements.md).

Installed SkellyForge, core's lockfile and the clean sibling checkout all agree on
`0ede33e0a6e323dcd4f4b9de2e1b4fc9eff5e41d`. This is not a stale installed dependency.

Current core fitting and reconstruction loop separately over frames and models.
SkellyForge's active scalar vector rotation still performs two general NumPy cross
products per vector. A fresh profile of the first 100 frames of the preserved sample
made 35,396 scalar quaternion-vector rotations and 89,692 cross-product calls.
These are call counts from instrumentation, not a forecast of achievable speedup.

An isolated replay of all 1,108 preserved sample frames took 7.782 seconds fitting
and 33.101 seconds reconstructing. That historical saved source is not proven
identical to the latest app's inputs and settings; the difference is not evidence
that contention alone explains the app timings. Profile times include instrumentation
overhead and must not be compared directly to unprofiled stage durations.

## Next optimization targets

1. Batch independent joint-attachment and landmark rotations inside one pose.
   The existing batch rotation helper computes an N-by-M Cartesian product; paired
   rotations require the correct paired contract, not extracting its diagonal.
2. Avoid general cross-product machinery for tiny scalar rotations where the
   surrounding temporal dependency prevents batching. Preserve numerical checks.
3. Measure and reduce repeated point mapping and skeleton hydration between fitting
   and reconstruction. Fitting excludes interpolated evidence, so blindly reusing
   reconstruction inputs would change scientific behavior.

Temporal roll resolution and parent-child traversal have real dependencies. Their
order must remain intact while independent arithmetic is batched. No SkellyForge
source, dependency version or numerical reconstruction behavior was changed during
this audit. Implementing these changes is the next independently reviewed dependency
stage, followed by core parity and full-run measurements.

## Completed-run display

Each operation now carries backend-measured elapsed seconds and, when its successful
motion-frame count is known, seconds per motion-capture frame. The UI places those
numbers immediately before the completion status in each row. The recording header
also shows total duration and the synchronized-frame denominator. No camera-image
count is used as a substitute, and missing measurements remain absent.

Validation: 19 focused backend tests, six frontend tests, three browser tests and
TypeScript passed. The browser checks cover 440px and 900px cards. New measurements
are available on subsequent runs after loading the changed backend/frontend;
already-retained snapshots have no historical timings to reconstruct.
