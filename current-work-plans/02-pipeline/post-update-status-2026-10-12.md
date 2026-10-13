# Application check after Forge update — 2026-10-12

Owner clarification: old generated reference files are disposable. Do not implement
format migration to reuse them; regenerate from synchronized videos with fresh
calibration. The historical-input failure below records what was observed, not a
compatibility requirement. The dataset workflow now replaces fresh results and
retains only the immediately previous recording for comparison.

Evidence: `C:/Users/jonma/skellylogs_data/logs/log_2026-10-12T18_30_25ms100_gmt-4.log`.
Test task `430362be-5350-4d8a-862f-e1458a2fbd6f` completed at 18:31:28;
sample task `8f4ee1b1-e8e2-47b1-be42-56f56491580e` completed at 18:35:07.
Installed Forge and core lock agree on `f5404db5791c69afedf95652ef7cebca316e5ec0`.

| Measurement | Test recording | Sample recording |
| --- | ---: | ---: |
| Selected implementation | typed_dataflow | current |
| Motion frames (three cameras) | 222 | 1,108 |
| Whole run, including exports | 45.368 s | 200.662 s |
| Whole run / motion frame | 204.4 ms | 181.1 ms |
| Load and track, including setup/finalization | 14.274 s | 118.919 s |
| Inference calls alone | 11.417 s | 37.714 s |
| Match/triangulate operation | 3.541 s | 3.990 s |
| Skeleton dimension fitting | 3.191 s | not separately reported |
| Skeleton reconstruction operation | 6.119 s | 29.275 s |
| Scientific exports | 3.078 s | 12.231 s |
| Blender exports | 13.968 s | 23.908 s |
| Combined concurrent export interval | 13.970 s | 23.911 s |

Rows overlap. The existing pipeline's reconstruction row has different scope from
the graph's separate fitting/reconstruction rows. Do not compare those as identical
operations. Both requests used RTMW-x-l 256x192, YOLOX-m, and ChArUco.
The sample's existing coordinator spent 77.705 s waiting for annotation, versus
39.163 s waiting for inference and 0.030 s waiting for video reads. This is evidence
of the existing pipeline's blocking, not evidence that the new graph has that wait.

Against the earlier graph test run (62.919 s), this test run is 27.9% shorter;
its skeleton reconstruction is 55.1% shorter (13.641 to 6.119 s). These are
observational app runs, not controlled repeated benchmarks. The earlier sample
was a graph run, so its 224.391 s is not a same-implementation baseline.

Both sessions registered CUDA first. Test explicitly requested CUDA. Sample
requested TensorRT but fell back to CUDA; TensorRT options were ignored. Provider
registration is not per-kernel GPU profiling. Scientific export validation succeeded;
all six checkpoint writes reported zero scalar validation fallback rows. Blender
logged saved scenes. No processing failure appears in the two run summaries.
Playback afterward logged two HTTP 416s and a stale-revision HTTP 409, followed
by refreshed manifest/video requests. This deserves playback-refresh coverage,
but does not indicate failed processing. Files were not independently revalidated
by this log audit.

## Coverage and remaining integration

- Existing saved-stage tests cover retained upstream data, cancellation, missing
  inputs, no detector startup, recovery after reconstruction failure, and run
  retention/replacement provenance.
- Expanded real-recording replay to both prepared datasets: filter, refit dimensions,
  reconstruct with a changed skull anchor, repeat that reconstruction, compare
  numerical rows, retain scale fits/timing/reference definitions, and protect source
  hashes. JUnit records operation times. Tests operate on temporary copies.
- Eight existing application-routing and tracker-matrix unit tests passed after
  the update. These use mocks for execution; they do not certify model inference.
- After owner-authorized `uv sync --locked --group dev`, the focused suite passed:
  **23 passed, 8 dependency type-hint deprecation warnings, 143.12 s**. No skips.
  Two old worker mocks needed a real performance report and explicit Blender-off
  configuration so numerical-only tests do not invoke external export setup.
- The first run against default prepared files failed: those historical files
  contain `solver`, `skeleton_fit` and `LINKAGE_DISPLACEMENTS` definitions rejected
  by the current reader. They were not changed or stripped. The successful replay
  instead used copies of the user's latest app outputs under ignored
  `.test-artifacts/app-run-replay`, selected with `FREEMOCAP_PROVENANCE_PREPARED_ROOT`.
  This validates current-output replay, not compatibility with those historical files.
- Detector/backend comparisons exist for default configurations, separately from
  full pipeline acceptance. Arbitrary model variants and model-switching full runs
  are not covered by that matrix.
- The application graph rejects saved-stage starts. The standard dataset workflow
  still rejects `--implementation graph`, although separate graph comparison tools
  exist. Full graph acceptance needs integration with the existing workflow.
- New cross-frame Forge APIs have no core callers yet. Optimizations to existing
  APIs are active; merely updating the dependency does not enable the new APIs.

Recommended order: regenerate disposable prepared data from source videos; integrate the graph into
the existing reference workflow; run matching graph configurations on both datasets;
add graph saved-stage starts with the same retention/cancellation checks; extend
full-run detector/model configuration coverage. Keep actual numerical validity and
missingness comparisons separate from performance measurements.

## Measured saved-stage replay

| Start stage | Test seconds | Sample seconds |
| --- | ---: | ---: |
| Filtering through reconstruction and save | 6.606 | 31.152 |
| Scale fitting through reconstruction and save | 6.451 | 29.989 |
| Reconstruction with skull anchor and save | 5.340 | 24.934 |
| Identical reconstruction rerun and save | 5.342 | 25.451 |

These are individual restart-call wall times, including reading and writing the
copied recording and all downstream numerical work. They are not isolated math
kernel timings. Both repeated outputs matched exactly for landmarks and world
rotations. Tests verified raw points, coordinate definitions and timing stayed
unchanged; reconstruction retained scale fits; copied source hashes stayed intact.
Raw log and JUnit properties are in `.test-artifacts/post-update-stage-checks.txt`
and `.test-artifacts/post-update-stage-checks.xml`. The test-file syntax check passed.

## Fresh reference regeneration after owner clarification

Auditing the actual workflow found that full fresh runs still checked previous
generated hashes/calibration before starting, history grew without pruning, and
the older `prepare(fresh=True)` helper discarded a successful fresh result when
an accepted result already existed. These behaviors are corrected in the existing
workflow and storage helpers. Fresh work does not parse old generated data;
saved-stage work still validates the data it consumes. New results are validated
before replacement; one previous output survives for comparison and older history
is deleted using guarded local paths. Attempt diagnostic logs remain available.

The source recordings had no board sidecars. Reference inspection now uses the
already-established catalog definition (7x5, 58 mm squares) when a sidecar is absent,
and writes that definition into the generated recording. Conflicting supplied
metadata is still rejected. This is known reference scale, not inference from pixels.

`python -B -m freemocap.tools.datasets process-all` completed on the normal prepared
root with fresh calibration, RTMPose, numerical reconstruction, saved-scene export
and validation. Test worker lifecycle: **62.137 s**; sample: **210.550 s**. These
include calibration, validation and shutdown, unlike the earlier app-only numbers.
Both use the existing pipeline; this does not add graph workflow integration.
Both roots contain exactly one history directory. All six original video hashes
still match their pre-run hashes. Generated outputs replaced the old prepared files;
no compatibility migration was added. Workflow regression tests: **56 passed**.
Full regeneration log: `.test-artifacts/reference-regeneration.txt`.

Timing clarification: both regenerated datasets explicitly record
`pipeline_implementation=current`, not `typed_dataflow`. Mocap task time alone
was **37.257 s test / 135.506 s sample**. Calibration snapshot intervals were
11.023 s / 46.976 s; the rest of worker lifecycle includes setup, validation and
shutdown. These standard runs requested Blender but no scientific CSV/NPY/NPZ
formats, whereas the earlier app runs requested those formats. Neither whole-run
nor mocap-only numbers are a controlled graph-versus-current comparison.
The existing coordinator still reported annotation waits of 10.172 s / 49.421 s.

After regeneration, the expanded stage, provenance, routing and tracker-matrix
suite plus both real-reference provenance consumers passed: **25 passed, no skips,
8 dependency warnings, 176.81 s**. Evidence is
`.test-artifacts/fresh-reference-replay.txt` and `fresh-reference-replay.xml`.
This run used the normal prepared root, not the temporary app-output substitute.
