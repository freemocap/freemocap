# Detailed full-workflow benchmarks — 2026-11-03

[CoreML correction and paired ms/frame–FPS measurements](COREML-RESULTS-2026-11-03.md) supersede the CPU-only hardware-performance interpretation below. Historical measurements are retained.

Apple M4 Pro (12 CPU cores), 24 GiB RAM; macOS 26.6.2; CPUExecutionProvider for RTMW and YOLOX. Three 720×1280 videos per dataset. Existing standard dataset workflow, fresh calibration, full Blender export and reopened-scene validation. Cached models and managed Blender package; other desktop apps and agents active. One new observation per dataset, not a median.

The summary below is derived from the archived JSON records. Full tables retain all stages and precision: [test report](results/2026-11-03-mac-mini-m4-pro-24gb-standard-stats-test-01.md), [sample report](results/2026-11-03-mac-mini-m4-pro-24gb-standard-stats-sample-01.md).

| Measurement | Test data | Sample data |
|---|---:|---:|
| Synchronized frames | 222.000 | 1108.000 |
| Camera images | 666.000 | 3324.000 |
| Full worker seconds | 62.614 | 244.811 |
| Full worker amortized ms/frame | 282.045 | 220.949 |
| Full worker camera images/s | 10.637 | 13.578 |
| Posthoc processing seconds | 50.413 | 205.729 |

## Stage costs

These are wall-clock spans. Rows overlap: inference is inside load/track, which is inside mocap; annotation also overlaps tracking. Do not sum rows. Per-frame costs divide total span time by synchronized-frame count.

| Stage | Test s | Test ms/frame | Sample s | Sample ms/frame |
|---|---:|---:|---:|---:|
| Blender preparation (cached) | 1.361 | 6.130 | 1.376 | 1.242 |
| Fresh calibration | 6.007 | 27.060 | 24.183 | 21.826 |
| Mocap workflow span | 50.652 | 228.162 | 206.003 | 185.924 |
| Load and track | 39.832 | 179.424 | 174.436 | 157.433 |
| Inference session setup | 1.013 | 4.561 | 0.970 | 0.876 |
| Inference batches | 38.719 | 174.408 | 173.138 | 156.261 |
| Match and triangulate | 0.376 | 1.694 | 1.800 | 1.624 |
| Trajectory filter stage | 0.009 | 0.041 | 0.050 | 0.045 |
| Align reference | 0.242 | 1.091 | 1.261 | 1.138 |
| Fit model dimensions | 0.070 | 0.317 | 0.151 | 0.136 |
| Reconstruct skeletons | 0.555 | 2.498 | 2.340 | 2.112 |
| Save observations | 0.234 | 1.053 | 1.634 | 1.475 |
| Save spatial data | 1.013 | 4.562 | 4.216 | 3.805 |
| Save recording | 0.733 | 3.300 | 3.060 | 2.761 |
| Annotate camera 0 | 3.453 | 15.552 | 14.024 | 12.657 |
| Annotate camera 1 | 3.450 | 15.539 | 13.899 | 12.544 |
| Annotate camera 2 | 2.602 | 11.719 | 10.440 | 9.422 |
| Blender export | 4.283 | 19.292 | 6.693 | 6.041 |
| Numerical validation | 0.212 | 0.954 | 0.859 | 0.775 |
| Blender scene validation | 2.563 | 11.547 | 10.050 | 9.070 |
| Output acceptance | 0.013 | 0.058 | 0.065 | 0.059 |
| Shutdown | 0.001 | 0.002 | 0.001 | 0.000 |

Filtering is disabled by the existing test-data preset and enabled for sample data; the filter-stage span includes dispatch/no-op overhead when disabled. Outer worker timing also includes Python imports, process startup/exit and bookkeeping not individually measured by these phases.

## Inference call statistics

Each call processes three camera images. After-first mean excludes exactly the first call; it is not proof of steady state. Amortized ms/image is a throughput cost, not individual-image latency.

| Dataset | Calls | Mean ms/call | First ms | After-first mean ms | Max ms | Amortized ms/image |
|---|---:|---:|---:|---:|---:|---:|
| Test | 222.000 | 174.408 | 857.169 | 171.319 | 869.683 | 58.136 |
| Sample | 1108.000 | 156.261 | 875.000 | 155.612 | 897.134 | 52.087 |

Inference accounts for 84.2% of the sample posthoc wall interval. It dominates the measured cost; reconstruction and triangulation are much smaller. The first inference call is substantially slower than the remaining-call mean. These observations do not establish GPU performance, a Windows comparison, or a hardware-only cause.

## Reporting repair and verification

The existing dataset summary parser silently dropped the current bordered stage table. Regression coverage reproduced that failure. The normal workflow now prints/saves all stage rows, emits full-precision structured events and saves versioned timing reports; the benchmark wrapper archives them and compares stage costs. Both historical display formats remain readable. Missing latency percentiles are explicitly unavailable. Existing historical records have not been rewritten.

52 focused tests passed, including normal workflow replacement/failure behavior, event/table round-trip precision, stage comparisons and failure preservation. Ruff and diff checks passed. Both new full standard runs passed their existing numerical, Parquet, Blender export and reopened-scene acceptance checks. Saved timing sidecars match readiness records. Original shared Core/Cam checkouts retain their pre-existing lockfile changes.

Camera results and remaining cross-platform issues are unchanged: see the [baseline report](RESULTS-2026-11-03.md) and [compatibility audit](COMPATIBILITY-AUDIT-2026-11-03.md).
