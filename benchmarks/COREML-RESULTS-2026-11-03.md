# Mac acceleration diagnosis and measured correction

The previous sample inference measurement was CPU execution. Core graph Auto selected CUDA when available and otherwise forced CPU, even though this Mac’s installed ONNX Runtime 1.31.1 advertises CoreML. A regression test reproduced the wrong selection. Core now retains its existing CUDA preference over TensorRT compilation and delegates other hardware to Tracker’s existing accelerator discovery. Explicit selections remain unchanged. No dependency installation, detector recipe change or local model workaround was needed.

Both corrected full standard runs passed the existing numerical, Parquet, Blender export and reopened-scene validation. These are fresh three-camera reference runs on the same M4 Pro/24 GiB machine, with cached assets and other apps/agents active. CPU and CoreML observations were not simultaneous, randomized or idle-machine trials; ratios describe these observations, not a universal speedup.

## Inference: paired units

One synchronized frame contains three camera images. Each inference call in these runs processes that three-image set.

| Dataset | CPU | CoreML | Observed throughput ratio |
|---|---:|---:|---:|
| test | 174.41 ms/frame · 5.73 FPS | 36.82 ms/frame · 27.16 FPS | 4.74× |
| sample | 156.26 ms/frame · 6.40 FPS | 37.56 ms/frame · 26.62 FPS | 4.16× |

## Sample: stage and full-run costs

FPS below is the reciprocal of amortized milliseconds per synchronized frame for that span. It is not live playback FPS. Spans overlap and cannot be added.

| Span | CPU seconds | CPU ms/frame · FPS | CoreML seconds | CoreML ms/frame · FPS |
|---|---:|---:|---:|---:|
| Full worker, including calibration and validation | 244.811 | 220.95 ms/frame · 4.53 FPS | 122.753 | 110.79 ms/frame · 9.03 FPS |
| Posthoc processing | 205.729 | 185.68 ms/frame · 5.39 FPS | 82.950 | 74.86 ms/frame · 13.36 FPS |
| Load and track, including session setup | 174.436 | 157.43 ms/frame · 6.35 FPS | 48.020 | 43.34 ms/frame · 23.07 FPS |
| Inference calls | 173.138 | 156.26 ms/frame · 6.40 FPS | 41.620 | 37.56 ms/frame · 26.62 FPS |
| Session setup | 0.970 | 0.88 ms/frame · 1142.11 FPS | 6.024 | 5.44 ms/frame · 183.93 FPS |
| Fresh calibration | 24.183 | 21.83 ms/frame · 45.82 FPS | 24.883 | 22.46 ms/frame · 44.53 FPS |
| Match and triangulate | 1.800 | 1.62 ms/frame · 615.72 FPS | 1.563 | 1.41 ms/frame · 708.71 FPS |
| Reconstruct skeletons | 2.340 | 2.11 ms/frame · 473.52 FPS | 2.989 | 2.70 ms/frame · 370.69 FPS |
| Save spatial data | 4.216 | 3.81 ms/frame · 262.79 FPS | 5.031 | 4.54 ms/frame · 220.23 FPS |
| Blender export | 6.693 | 6.04 ms/frame · 165.54 FPS | 6.592 | 5.95 ms/frame · 168.08 FPS |
| Blender scene validation | 10.050 | 9.07 ms/frame · 110.25 FPS | 10.079 | 9.10 ms/frame · 109.93 FPS |

Session setup grew from about one second to six seconds with CoreML. The much lower inference cost more than offset it. Calibration and Blender validation remained substantial independent costs, which is why full-worker throughput is lower than inference throughput. Annotation and saving also remain part of processing; complete reports retain those overlapping spans.

## Sample inference startup and variation

| Measurement | CPU ms/frame · FPS | CoreML ms/frame · FPS |
|---|---:|---:|
| Mean | 156.26 ms/frame · 6.40 FPS | 37.56 ms/frame · 26.62 FPS |
| First call | 875.00 ms/frame · 1.14 FPS | 112.79 ms/frame · 8.87 FPS |
| Mean excluding first | 155.61 ms/frame · 6.43 FPS | 37.50 ms/frame · 26.67 FPS |
| Slowest call | 897.13 ms/frame · 1.11 FPS | 158.11 ms/frame · 6.32 FPS |

CPU: **52.09 ms/camera image · 19.20 images/s** amortized. Per-image cost is not individual-image latency.

CoreML: **12.52 ms/camera image · 79.87 images/s** amortized. Per-image cost is not individual-image latency.

## Hardware evidence and limits

Both models logged CoreMLExecutionProvider followed by CPUExecutionProvider. ORT reported 405 of 456 RTMW graph nodes supported by CoreML in two partitions, and 373 of 424 YOLOX nodes in two partitions. Those are support counts, not time fractions or proof every operator executes on GPU. The source processing logs are hash-identified in each archived benchmark.

Tracker’s existing RTMW model spec requests CPUAndGPU. Its model-spec contract documents that option for models whose Neural Engine compilation fails with error -5. This fix preserves that established model configuration. CoreML compute-unit choices distinguish CPU/GPU from all compatible units, and compute-plan profiling can expose device dispatch; simply registering CoreML does not prove all work runs on the GPU [@ortCoreMLProvider]. No claim of Neural Engine utilization or parity with a particular NVIDIA GPU is made.

The UI harness independently reported 11–12 minute multi-case reference suites, repeated per design commit and sometimes overlapping other processing. Its explicit-CPU numerical sample runs (210–218 seconds, exports disabled) and cumulative recorded replay FPS are different workloads. Those observations help explain perceived waiting but are excluded from these benchmark ratios. Its Blender failures are from a different checkout without this branch’s validated automatic-packaging fix.

## Records and validation

Normal and benchmark stage tables now always pair ms/frame with frames/s and ms/image with images/s. Raw timing JSON remains unchanged; rates are derived from recorded counts and durations. Existing stage-record Markdown was regenerated with paired rate columns. Use individual observations or matching provider/software subsets: combining CPU and CoreML runs into one machine median hides this correction.

84 focused tests passed, including the reproduced CoreML selection bug, preservation of CUDA preference and explicit choices, paired rate arithmetic, and existing workflow/failure reporting checks. Both full reference runs passed. Ruff and bibliography checks passed. Hardware validation covers this Mac; Windows CUDA preference is covered by regression tests, not a new Windows hardware run.

- test CPU: [full table](results/2026-11-03-mac-mini-m4-pro-24gb-standard-stats-test-01.md), [machine-readable record](results/2026-11-03-mac-mini-m4-pro-24gb-standard-stats-test-01.json).
- test CoreML: [full table](results/2026-11-03-mac-mini-m4-pro-24gb-coreml-standard-test-01.md), [machine-readable record](results/2026-11-03-mac-mini-m4-pro-24gb-coreml-standard-test-01.json).
- sample CPU: [full table](results/2026-11-03-mac-mini-m4-pro-24gb-standard-stats-sample-01.md), [machine-readable record](results/2026-11-03-mac-mini-m4-pro-24gb-standard-stats-sample-01.json).
- sample CoreML: [full table](results/2026-11-03-mac-mini-m4-pro-24gb-coreml-standard-sample-01.md), [machine-readable record](results/2026-11-03-mac-mini-m4-pro-24gb-coreml-standard-sample-01.json).
