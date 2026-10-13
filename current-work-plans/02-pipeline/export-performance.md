# Export execution and progress - 2026-10-12

The application runs Blender and scientific file exports independently after the
saved recording is available. Two supervising threads are sufficient for these
two destinations. This is not a claim about total process thread counts: Blender,
Arrow and NumPy may use native threads of their own.

Scientific CSV/NPY/NPZ exports reuse each channel's assembled arrays. Tall CSV and
scientific exports share a publication manifest and exclusive lock, so their
transactions remain serialized. Increasing the number of workers without changing
that ownership would cause conflicts rather than useful parallelism.

Each export reports its own outcome. A failed branch does not prevent independent
work from completing. Overall completion waits for all requested exports. Blender
subprocess cancellation now kills and reaps the child; this does not introduce
transactional publication for Blender files. Interrupted Blender output can still
remain on disk, and is never reported as successfully completed. First-time package
resolution retains its existing synchronous behavior.

## Measured scientific export improvement

Saved sample recording: 1,108 motion-capture frames, three cameras, 9,310,524 Parquet
rows. Requested products: landmarks, filtered/raw 3D points, 2D overlays and segment
poses; formats: wide CSV, NPY and NPZ. Output size approximately 123 MB.

| Work | Original isolated run | Optimized isolated run |
| --- | ---: | ---: |
| Complete scientific export | 35.510 s | 7.132 s |
| Assemble arrays from Parquet | 22.330 s | 2.154 s |
| Validate CSV files | 5.734 s | 1.377 s |

Two final optimized runs took 7.136 and 7.132 seconds. This is about 80% less
export time, or five times faster, on this saved sample and machine. These are
export-only runs, not a new full-pipeline measurement. The earlier live application's
57-second export interval is not the controlled baseline for this comparison.

Changes replace per-measurement Python indexing with Arrow/NumPy batches, use
bounded blocks for CSV formatting and validation, read only needed timing columns,
and skip Parquet row groups only when their statistics prove they cannot match.
Missing statistics fall back to reading/filtering. Schema information is resolved
once per scan. No scientific validation was removed.

All 20 CSV/NPY payloads and all 11 NPZ measurement members matched the original
outputs byte-for-byte. Source Parquet SHA-256 remained unchanged. Metadata and ZIP
container bytes contain timestamps and are not claimed to be identical.

Local evidence: `.test-artifacts/export-vectorization/final-{2,3}/report.json`.
Repeat with `python -m freemocap.tools.datasets.benchmark_exports --help`.

## Measured concurrent exports

Using the optimized scientific exporter, the same saved recording and an existing
verified Blender profile:

| Work | One supervising worker | Two supervising workers |
| --- | ---: | ---: |
| Scientific files | 7.036 s | 7.448 s |
| Blender scene, FBX and BVH | 18.668 s | 18.266 s |
| Overall elapsed export interval | 25.874 s | 18.283 s |

Overlapping destinations saved another 7.590 seconds (29.3%). Scientific export
slowed slightly while sharing resources, but overall elapsed time improved. Both
trials produced nonempty Blender, FBX and BVH files. The 20 CSV/NPY files and 11 NPZ
array members matched between trials. Blender file byte identity was not tested.

This was one sequential-then-concurrent pair, not a controlled cache/order sweep
or a universal thread-count optimum. Blender profile preparation was excluded from
both trials; no package installation or environment change occurred. The tool
refuses to install a missing profile. More supervising threads cannot help this
two-destination execution topology without splitting ownership first.

Local evidence: `.test-artifacts/export-overlap-final/comparison.json`.
Repeat with `python -m freemocap.tools.datasets.compare_export_concurrency --help`.

## Progress and diagnostics

`TaskSnapshot.operations` is a complete backend-owned list of independently
executing operations. Each has an identity, display label, state, optional measured
fraction/counts/unit, and optional detail. The backend retains completed siblings
and publishes cumulative snapshots before the delivery layer coalesces updates.
The frontend displays stacked bars directly from these snapshots. Unknown progress
is indeterminate; it is never an invented percentage. Graph processing, per-camera
annotation, scientific exports and Blender can appear independently.

The existing performance report now includes individual graph-operation durations,
individual export durations, and the elapsed export interval. Overlapping durations
must not be added together. Scientific exports also log assembly, writing,
compression and validation timings and include them in their result.

Regression coverage includes independent failure, true export overlap, cancellation
and subprocess cleanup, replayable progress snapshots, malformed data, duplicate
measurements, missingness, units, timestamps, signed zeros, dictionary columns and
Parquet files with absent/mixed row-group statistics. UI tests cover snapshot
replacement, completed siblings, cancellation and multiple independent bars.

Final integrated backend check: 98 tests passed across operation snapshots,
application routing, recording graph failures, export orchestration, Blender
execution/preparation, scientific export API, batched validation and data products.
Frontend typecheck, four reducer/schema/render tests and two stacked-bar browser
tests passed, including a styled narrow-card check. Python test tooling came from an existing test
environment, appended after core's installed dependencies; no installation or
dependency override was performed. Existing deprecation/config warnings remain.

The changes apply on backend/frontend restart; an already-running process does not
load edited Python modules automatically. No recording outputs were replaced during
these measurements: benchmark tools use fresh copies under ignored test artifacts.
