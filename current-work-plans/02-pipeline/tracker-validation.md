# Tracker adapter validation — 2026-10-11

The bounded streaming adapter passed same-backend numerical comparisons for the
app-default ChArUco CPU, MediaPipe CPU, RTMPose CPU and RTMPose CUDA configurations
on both reference recordings. Each run covered three cameras: 222 frames per
camera for test data and 1,108 for sample data. All eight comparisons had zero
numeric differences and zero structural/missingness differences. RTMPose used
RTMW-x-l 256×192 plus YOLOX-m; MediaPipe included body, hands and face.

This validates the loading-to-tracking boundary against the existing inference
service, not full posthoc scientific acceptance. No accepted recording outputs
were saved. The existing production pipeline and realtime callers are unchanged.

| Recording | Backend | Baseline diagnostic wall seconds | Adapter diagnostic wall seconds |
| --- | --- | ---: | ---: |
| Test, 3 × 222 | ChArUco CPU | 10.77 | 11.49 |
| Test, 3 × 222 | MediaPipe CPU, explicit timeline | 50.15 | 43.15 |
| Test, 3 × 222 | RTMPose CPU | 39.75 | 40.88 |
| Test, 3 × 222 | RTMPose CUDA | 15.35 | 15.12 |
| Sample, 3 × 1,108 | ChArUco CPU | 48.80 | 63.07 |
| Sample, 3 × 1,108 | MediaPipe CPU, explicit timeline | 208.37 | 264.20 |
| Sample, 3 × 1,108 | RTMPose CPU | 128.84 | 155.55 |
| Sample, 3 × 1,108 | RTMPose CUDA | 104.99 | 130.16 |

These are single ordered passes with unequal diagnostic I/O and setup effects,
not a speedup benchmark. For example, sample CUDA adapter inference itself took
81.132 seconds (73.224 ms per three-camera batch), while waiting for camera batches
took 0.115 seconds total. The wait is not total video-reading CPU time: loading
overlaps inference. Repeated symmetric benchmarks remain a performance gate.

## Problems exposed

**MediaPipe processing-time fallback.** The initial test-data comparison failed:
109,257 numeric values exceeded 1e-6, with 4,536 structural/missingness differences.
The maximum mixed-unit absolute difference was 210.3263. Supplying the same
relative recording timeline to both paths produced exact parity on both datasets.
The optional inference-request timestamp now enables that behavior in the adapter;
existing callers retain their old defaults. This deliberately corrects temporal
semantics and is not parity with the old wall-time fallback. The recording timeline
may be measured or FPS-inferred through the existing resolver
[@skellytrackerBatchSessions2026].

**RTMPose CPU and CUDA are not interchangeable numerically.** Their independent
sequential-read baselines already differ. Across 427,987 matched visible points in
sample data, XY distance was median 1.203 px, p95 3.855 px, p99 8.195 px and maximum
378.896 px; 511 point visibility/finite masks differed. The largest matched-visible
outlier was camera 2, frame 117, `left_hand_middle_finger3` (CPU visibility 0.592,
CUDA 0.516). Detector-schedule flags did not differ. This has not been attributed
to a specific kernel, precision setting or downstream decision. Do not dismiss
it as harmless roundoff or claim cross-backend scientific equivalence. Investigation
belongs at the existing detector/provider boundary before making that claim.

**MediaPipe CUDA is unsupported.** Installed detector options do not select a GPU
delegate, so a CUDA pass cannot honestly be reported. ChArUco uses CPU. RTMPose
sessions registered the requested provider first for both models; individual
kernel placement was not profiled. Tested CUDA hardware was an RTX 3090.

## Reproduce and interrogate

Commands and report semantics are in the
[dataset tool documentation](../../freemocap/tools/datasets/README.md#tracker-adapter-parity-and-timing).
`tracker_matrix` runs each case in an isolated process, retains failed evidence,
and records CPU/CUDA differences separately from same-backend regression parity.
It reports unsupported configurations without substituting a CPU run for CUDA.

Local evidence is retained under `.test-artifacts/tracker-matrix/`: `report.md`,
per-case JSON/text reports and native logs, private baseline observations, the
original failing `test-mediapipe_cpu` comparison, and
`sample-cpu-versus-cuda.json`. These generated files are ignored, not committed.
The reusable comparison code and tests are source files awaiting review.

The next acceptance boundary remains saving tracking products through the existing
recording acceptance machinery, followed by complete scientific and annotation
graph comparisons. This experiment does not authorize replacing production routes.
