# Isolated component measurements

Measured 2026-10-11 on the complete sample: 1,108 motion-capture frames, three cameras, RTMPose CUDA plus board tracking, human and board reconstruction, NPZ export, and three annotated videos. No frame cap. Existing handlers and scientific algorithms, executed one at a time for diagnosis. Internal native workers and camera batching remain enabled.

**Scientific check:** 36 saved channels matched the current scientific task exactly (maximum absolute error 0.0). All three annotated videos contain 1,108 frames.

## Unprofiled stage timings

| Operation | Isolated wall s | Process CPU s | Previous concurrent wall s |
| --- | ---: | ---: | ---: |
| Load videos and track (CUDA + board) | 48.246 | 140.453 | 58.777 |
| Annotate camera 1 | 18.712 | 90.906 | 27.032 |
| Annotate camera 2 | 18.521 | 94.203 | 26.745 |
| Annotate camera 3 | 18.877 | 91.312 | 22.380 |
| Match cameras and triangulate | 3.624 | 3.562 | 9.204 |
| Prepare 2D save request | 0.285 | 0.297 | 0.586 |
| Filter 3D trajectories | 0.201 | 0.188 | 0.476 |
| Save 2D observations | 2.880 | 2.828 | 8.969 |
| Align coordinate frame | 2.093 | 2.062 | 4.290 |
| Prepare skeleton inputs | 0.008 | 0.000 | 0.015 |
| Prepare 3D save request | 0.001 | 0.000 | 0.003 |
| Fit model dimensions | 8.333 | 8.250 | 19.204 |
| Save 3D tracking results | 4.787 | 5.172 | 77.237 |
| Reconstruct skeletons | 32.254 | 31.828 | 50.489 |
| Save complete recording | 7.336 | 8.781 | 20.304 |
| Export scientific arrays | 4.230 | 12.062 | 6.673 |

CPU sums all native/Python threads in this process; it excludes GPU execution and child processes. The historical concurrent column is orientation, not a controlled speedup estimate: it predates the two save-path fixes, uses annotation processes, and was measured under different host conditions. Isolated timings are single full-recording measurements, not distributions. No other diagnostic workload was intentionally run beside the timed graph.

Serial diagnostic wall time: 170.411 seconds. This deliberately includes all three annotation jobs sequentially and is not a production scheduling recommendation or a theoretical optimized runtime. The reported scientific-completion timestamp also includes earlier serial annotation work and must not be interpreted as scientific-only cost.

## Loading and tracking

- Video 1, read only: median 1.930 s, range 1.922-1.956 s across three rotated trials; all 1,108 frames read.
- Video 2, read only: median 1.823 s, range 1.818-1.943 s across three rotated trials; all 1,108 frames read.
- Video 3, read only: median 1.860 s, range 1.824-1.915 s across three rotated trials; all 1,108 frames read.
- graph.camera_batch_wait: 0.062 s across 1109 calls.
- inference.queue_wait: 0.130 s across 1108 calls.
- inference.session_setup: 1.671 s across 1 calls.
- inference.process_batch.images=3: 45.062 s across 1108 calls.

The batch inference duration contains both requested tracker stages; it is not a GPU-kernel-only measurement. Camera reading overlaps inference in the existing adapter. Read-only trials exclude tracking and do not retain frames; filesystem cache was not flushed.

## Annotation substeps

| Camera | Drawing s | Encode/write calls s | Total annotation s |
| --- | ---: | ---: | ---: |
| 1 | 6.776 | 9.399 | 18.712 |
| 2 | 6.621 | 9.376 | 18.521 |
| 3 | 7.546 | 8.870 | 18.877 |

Encode/write timers include submissions to the encoder, not all final flush/close costs. Remaining annotation time includes reading, initialization and finalization. Do not label the residual as pure disk time.

## Evidence and repeatability

- Full machine-readable report and parity: `.test-artifacts/performance/isolated-components/report.json`.
- Individual wall/CPU measurements: `components/components.json` beneath that directory.
- Video reading trials: `.test-artifacts/performance/isolated-video-reading.json`.
- Use the existing full-recording comparison CLI with `--isolate-components --annotation-execution thread`. Add `--profile-components` only in a separate profiling pass; profiler timings are not baseline measurements.
- The earlier storage-only and concurrency experiments, channel proportions and limitations are in [the performance audit](performance-audit.md).

## Current interpretation

The measured 3D-save cost in isolation is 4.787 seconds, not 77 seconds. Reconstruction is 32.254 seconds with 31.828 process CPU seconds, consistent with roughly one CPU core worth of work despite many present native threads. This does not by itself prove which code holds the GIL. The strongest remaining targets are interference between concurrently scheduled operations, reconstruction internals, and avoiding expanded repeated identifiers/repeated whole-recording save passes. Preserve all scientific checks and outputs while testing changes.

## Separate call-profile findings

A second replay used the previously captured real observations, both scientific
models and the actual graph handlers, one at a time. Tracking was replaced only
by that validated observation input; no tracking measurement is claimed for this
replay. All handlers completed. Profiles are under
`.test-artifacts/performance/isolated-profile-v2/profiles/`.

Profiler timings below include overhead and nested cumulative times overlap:

- Fitting: 42.2 million calls. Skeleton hydration accumulated 11.7 s and tracker
  mapping 6.4 s in a 20.2 s profiled operation (unprofiled baseline: 8.33 s).
- Reconstruction: 173.2 million calls for 1,108 frames x two models. There were
  891,349 calls to NumPy cross products, 344,376 quaternion-vector rotations and
  2,674,047 calls to NumPy moveaxis. Roll resolution, anchored pose synthesis and
  skeleton hydration are prominent callers. The profiled total is 77.5 s;
  **the unprofiled reconstruction baseline is 32.25 s**, not 77.5 s.
- Save 3D tracking: 4.79 s profiled. Parquet writing accumulated 2.53 s, sample
  validation 0.97 s and batch retention/construction/selection 1.06 s. Full writing
  includes those upstream generators; do not sum overlapping wrapper totals.
- Save complete recording: 7.94 s profiled, including 3.48 s in Parquet writing,
  1.28 s in sample validation and 2.66 s in checkpoint batch production.
- Scientific NPZ export: 4.21 s profiled, with 3.77 s in loading/ordering arrays and
  only about 0.15 s in NumPy array writing. Investigate repeat scans/materialization
  before tuning the zip compressor.

These are targeted candidates, not established speedups. In particular, many tiny
vector operations and per-segment object construction are worth investigating;
temporal roll state means indiscriminate frame parallelism can change science.
Changes inside SkellyForge or SkellyTracker require their own independently
reviewable repository work. No dependency implementation was edited here.

## Tracking profile scope and limitations

A full 3,324-image tracking-only check recorded 24 person-detector executions and
registered CUDAExecutionProvider first (CPU fallback also registered) for both
RTMW and YOLOX. This is session-provider evidence, not per-operator GPU placement.
The reliable unprofiled inference batch timing is 45.062 seconds from the main
isolated measurement. Per-model CUDA kernel durations are not measured here.

Two exploratory call profiles of tracking returned internally inconsistent
native-call self/cumulative accounting. A per-thread profiler wrapper did not
resolve that accounting, so neither profile's per-function duration is used to
assign body-versus-board cost or identify a tracking bottleneck. Their total
coverage/count/provider observations remain separate evidence. Next tracking
measurement should time detector boundaries directly or use an appropriate native
profiler. Do not infer a precise board/GPU split from those exploratory profiles.

## Validation and scope

Nine focused diagnostic/executor/pipeline tests passed. Production graph scheduling,
scientific algorithms, dependencies and storage format were not changed in this
measurement pass. The optional diagnostic CLI, reports and tests remain uncommitted.
The full parity run covers the sample dataset and this CUDA/body/board configuration;
it is not a new CPU/MediaPipe matrix or a repeated-trial whole-pipeline benchmark.
