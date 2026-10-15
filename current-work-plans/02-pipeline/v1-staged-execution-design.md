# V1 staged execution — design interview

2026-10-13. Code-grounded design notes; implementation is not authorized by the
interview alone. Pending recommendations below are not settled decisions.

## Existing agreements

- Scientific validity is mandatory. Missing required camera data never silently
  becomes a smaller-camera scientific result.
- Compute as soon as actual data dependencies permit, using batched numerical
  operations. Saving a stage must not become an artificial compute barrier.
- Complete independent requested outputs even when another branch fails.
  Annotation is a sink, never a scientific prerequisite.
- Validate completeness at scientific save boundaries. Temporary files are allowed;
  incomplete scientific results must not replace accepted results.
- The server owns execution and truth. HTTP controls requests; WebSocket clients
  display reports without deciding readiness or blocking processing.
- Reuse the existing recording contract, run/revision/attempt identities and
  overwrite/keep semantics. Do not invent another recording format or migrate old
  disposable reference outputs merely to support this work.

See [recording contract](../../RECORDING_CONTRACT.md), [glossary](../../CONTEXT.md)
and [foundations](dataflow-foundations.md).

## Verified implementation inventory

Paths relative to the repository root:

| Code | What exists / what it does not establish |
| --- | --- |
| `freemocap/core/tasks/mocap/mocap_task_config.py` | App start choices: observations, triangulation, filtering, scale_fit, reconstruction; base run and sensor group. No app stop-stage or keep selector in this config. |
| `freemocap/core/pipeline/posthoc/processing_request.py`, `stage_execution_plan.py` | Lower-level start/stop/keep plan, prerequisite signatures, descendant invalidation. Presence here does not establish application wiring. |
| `freemocap/core/pipeline/posthoc/saved_stage_processing.py` | Existing saved 3D readers and restart calculations. Numerical restart currently holds a recording write lock through computation and saves to the same base run. |
| `freemocap/core/pipeline/posthoc/mocap_pipeline.py` | Legacy triangulation restart reads saved observations and preserves the detector settings that produced them. Other saved starts call the numerical restart implementation. |
| `freemocap/core/pipeline/dataflow/application_pipeline.py` | V1 rejects saved starts; unconditionally resolves videos, board and calibration for a fresh run. |
| `freemocap/core/pipeline/dataflow/recording_pipeline.py` | Builds full fresh graph. Compute branches consume memory; saves are ordered observations -> spatial -> final recording. Saved raw and filtered points share the resolved aligned reference. |
| `freemocap/core/recording/parquet_storage/checkpoint_publication.py` | Reuses retained rows, removes invalid descendants, validates result ownership, checks metadata did not change, and uses existing recording publication. Keeping a run copies reusable rows into an independently readable result. |
| `freemocap/core/recording/data_descriptors/stage_provenance.py` | Saved effective settings, input signatures, software identity and base descriptor identity. |

The current app's saved numerical path constructs its plan directly rather than
calling `build_execution_plan`. Therefore the planner's signature checks cannot be
assumed to protect every app restart. Unify these checks at the saved-data source
boundary. Existing `test_recording_store.py`, `test_stage_provenance.py` and
`test_staged_mocap_processing.py` cover helper/legacy behavior, not V1 staged graphs.

## Technical work and risks

1. Compile only requested work and its prerequisites. Replace omitted upstream
   computation with typed saved-data sources; do not wrap the legacy coordinator
   in a graph node. Only start resources the selected graph needs.
2. Distinguish saved input identity from new settings. Changing tracker settings
   cannot relabel old observations. Changing calibration cannot reinterpret saved
   3D points. Verify frame/timing grids, camera identity, point names, model/fit
   definitions, units and reference frames before reuse.
3. Resolve alignment explicitly. Current saved raw 3D points are already in the
   resolved reference frame. A filtering restart must not apply alignment twice.
   Fresh execution aligns after filtering; equivalence needs testing, not assumption.
4. Keep data readiness separate from disk durability. Numerical consumers use
   in-memory outputs; save ordering protects shared persistent state. Do not add
   disk round trips between numerical nodes.
5. Control I/O cost. Existing checkpoint publication rewrites retained rows into a
   new file. Measure load/validation, compute, serialization, validation and final
   replacement separately. Avoid saving the entire recording after every tiny node.
6. Protect revisions. A restart must not publish against a base that changed while
   it ran. Existing locking is safe but broad; any shorter lock needs explicit
   immutable inputs plus a checked publication revision, not unlocked mutation.
7. Derive UI statuses from the backend plan: reused, scheduled, running, complete,
   blocked, failed. Existing files alone do not prove reusable scientific data.

## Decision tree — round 1 pending

Owner follow-up: proceed with implementation; replace the start dropdown with
checkboxes in the stage rows. Checking earlier work selects its downstream stages;
unchecking can express a shortened run. Keep the selection contiguous initially.
Removing the first checked stage reuses its saved result when available; removing
an interior/later stage shortens the run. No hidden stale-data holes are allowed.

Implementation status: checkbox selection and start/stop payload are implemented.
V1 supports observations/triangulation starts and observations/triangulation/filtering/
reconstruction finishes. Other selections remain blocked; this is not yet the
complete staged pipeline.

### Corrected scientific completion contract

The owner's correction supersedes the earlier unaligned-save proposal. Distinct
operations do not imply independently publishable scientific products. A requested
3D product includes its requested coordinate alignment before it may be saved as
complete. Never save unaligned points as a substitute for that completed product.

- Triangulation, trajectory preparation and alignment remain separate graph nodes.
  The early 3D save depends on their completed output, using the same scientific
  calculations and alignment policy as the full path.
- Alignment currently consumes prepared trajectories. A triangulation finish thus
  runs that preparation as a prerequisite, but publishes only raw aligned points,
  not a completed filtered channel. The UI explains this required preparation.
- An alignment exception blocks spatial saving. Completed tracking and independent
  requested annotation may still succeed. No change to the existing alignment
  algorithm's evidence/outcome policy is introduced here.
- Tracking-only graph construction does not read calibration. The application's
  broader UI calibration prerequisites still need an end-to-end check.
- V1 can restart triangulation from saved observations without resolving videos,
  scanning boards or starting trackers. Detector provenance is preserved.
- Early finishes exclude final file/Blender exports, as explained in the UI.
- Correction validation: 16 focused backend tests and 5 subtests passed, including
  nonzero requested transforms before early saves and failures blocking those saves.
  The earlier 28-test run and browser/type checks predate this correction; they are
  not evidence of full real-recording staged parity.

Still required: saved-3D sources, standalone fitted-model saves, full/staged parity
on both reference datasets, and V1 cancellation/revision tests. Alignment need not
be independently saved merely because it is a distinct computation.

- Q1 Initial user controls: implement start plus finish-at-stage together, or only
  start-and-run-to-end first? Recommendation: both, using the existing five visible
  scientific stages. Finish-at means exclude later scientific work from this request,
  not run later work and throw it away. Requested side outputs remain independent.
- Q2 Incompatible saved prerequisites: reject with the exact required earlier
  start, or automatically expand to earlier work? Recommendation: reject with a
  suggested corrected plan; never silently turn a short rerun into fresh tracking.

Dependent rounds: stage selection determines required save boundaries; mismatch
policy determines plan review UX. Then settle exposure of existing keep/overwrite,
side-output selection and freshness, failure retention, and cancellation boundaries.
Do not reopen scientific validity, annotation independence or client authority.

## Proposed validation (not yet run for this feature)

Use the existing test/sample reference dataset infrastructure. Compare each staged
result with the matching full-run settings and saved-input identity. Cover all five
starts and requested stops, changed filter settings, saved fit reuse, detector/model
changes, changed calibration and alignment, missing channels, stale revisions,
overwrite/keep, cancellation, and independent branch failures. Assert excluded work
never starts (including inference, board scan and video loading for 3D-only requests).
Report motion-capture frames, wall time, stage compute time, load/save/validation
time and waiting; do not add overlapping durations as if serial. Test that viewer
disconnects have no effect on execution. Numerical comparisons retain the established
rotation-aware contract and must not hide structural or validity mismatches.

## Real test-data stage matrix — 2026-10-13

The opt-in `freemocap.tools.datasets.stage_matrix` command now attempts all 15
contiguous ranges through the existing reference worker and application manager.
See [usage and scope](../../freemocap/tools/datasets/README.md). It is not part of
ordinary test collection. Each range uses an isolated recording copy; source
videos and calibration are checked unchanged at the end.

Executed on all 222 frames from three test-data cameras, with RTMPose/CUDA,
ChArUco, annotations, automatic alignment and a 1 Hz filter (test-data timing is
6 FPS; the normal 6 Hz cutoff would exceed Nyquist). Seven ranges passed; eight
were rejected by the current implementation. Rejections count as failures and
the command exits nonzero. This is not evidence that all staged processing works.

Successful ranges: tracking through tracking/triangulation/filtering/reconstruction,
and saved-2D restarts through triangulation/filtering/reconstruction. Every saved
channel matched the full run exactly, with maximum absolute difference 0.0. The
checks include complete sample grids, frame/timestamp identity, coordinate frames,
camera geometry, stage/channel coverage, executed operations and three complete
annotated videos. Full results also use existing reference validation and fit checks.

Application wall times were 25.28/26.26/25.04/25.62 seconds for those four fresh
ranges, and 13.20/13.34/13.45 seconds for those three restarts. Reported case totals
are larger because they include copying, process initialization, validation and
shutdown. These single runs are correctness tests, not controlled speedup claims.

The matrix found and verified a fix for saved-2D annotation looking only in
`videos/synchronized` while the source recording used `synchronized_videos`.
Restoration now locates the existing camera filename without decoding images.

Still blocking the complete matrix: saved-3D start sources and standalone
scale-fit saving. No legacy fallback hides these gaps. This matrix does not yet
cover changed detector/model configurations, keep/overwrite policy, cancellation,
concurrent revision changes, sample data, or Blender acceptance. Those remain the
separate validation requirements listed above. Local final reports are under
`.test-artifacts/stage-matrix/`; detailed case logs/copies are under the external
temporary directory `fmc-sm-1013d` named in `matrix.json`.


## Implemented staged graph paths � 2026-10-13

The implementation below supersedes the missing-capability inventory above.

- `saved_spatial_source.py` reads one complete saved 3D channel, its frame/timestamp
  identities, models, filtering report and coordinate reference under the recording
  lock. Saved fits must match the exact numerical inputs, model, reference and units.
- `saved_spatial_pipeline.py` compiles the requested filtering/fitting/reconstruction
  operations into the same typed graph executor. Saved-data loading is a graph
  operation with measured progress. These starts never open videos, scan a board,
  triangulate or realign points. Reconstruction-only loads the saved fits.
- `numerical_checkpoint.py` saves only the requested numerical stage products.
  It retains prerequisites and unrelated groups, invalidates affected destination results, and checks
  the recording revision again under its write lock before publication. Numerical
  computation does not hold the disk lock. Temporary Parquet files are validated
  before replacement; cancellation is checked before the final file replacement.
- Fresh and saved-2D graphs can finish after scale fitting and save reusable fits
  without executing skeleton reconstruction. Requested alignment remains required
  before saving completed 3D products.
- The application and stage checkboxes accept all five starts and finishes.
  The ordinary reference workflow accepts every `--from` choice and continues to
  reconstruction; the opt-in stage matrix exercises all fifteen start/finish pairs.

Saved-3D starts reuse existing annotations. They do not silently start detection
or annotation work. Final exports run only when reconstruction is requested.
### Processing run choice — revised contract

Processing stages owns **Starting data** (source run/group) and **Save results**:

- **Overwrite selected run:** save validated replacements atomically and remove
  dependent downstream data, fits and completion records from that Parquet run.
- **Keep selected run; create a new run:** retain the source run unchanged. Carry
  reusable prerequisites and provenance into the new run, then save the requested
  results there. Never copy invalid downstream results as newly completed work.

Changing controls does not write data. Each attempt has one destination run ID.
A new attempt reserves its `exports/run-<id>` folder so annotations from a failed
attempt cannot be overwritten by a later attempt that otherwise reuses its ID.
An empty reserved folder can remain after failure; it is not a completed run.
The first successful checkpoint creates the Parquet run. Later checkpoints update
that same run. Metadata changes by another writer reject publication. Application
attempts for one recording additionally use a fail-fast admission lock; graph
operations still execute concurrently.

Run 0 keeps ordinary output names. Later runs use `.run-<id>` suffixes and
`run-<id>` folders in their respective output locations: scientific exports under
`exports/`, annotations under `annotated_videos/`, and Blender scenes under the
recording root. Aligned calibration copies follow the scientific export run folder.
Overwriting a nonzero run uses those same paths. Existing exported files are not
removed by stage invalidation or journal recovery. They change only when a new
requested output replaces their matching filename. Only temporary staging and
publication journals are cleaned up.

Cancellation reaches both observation/spatial and numerical Parquet writers,
including the check before atomic replacement. Earlier successful checkpoints
remain if a later operation fails. Shared coordinate/model guards continue to
protect unrelated retained data; ordinary alignment reruns now invalidate their
own dependent results and can replace the coordinate definition safely.

The legacy pipeline remains available for comparison, but rejects new-run requests
rather than silently overwriting. The processing UI disables submission of that
unsupported combination. Both manual export panels use the source run selected
in Processing stages; automatic exports use the attempt's destination run.

This policy supersedes the temporary preserve-all-Parquet policy and its
102-test retention report. The real-data matrix below predates this revision.
Do not run a sample-data stage matrix for this work.

Verification of the revised run policy (2026-10-13): 172 focused Python tests
and 15 subtests passed in 56.01 seconds. Coverage includes saved-2D and saved-3D
restarts, source-run numerical preservation, destination-only invalidation,
failed-attempt run-ID reservation, cancellation before file replacement, and
run-specific annotation, scientific export, calibration-copy and Blender paths.
TypeScript checking passed. The stage-selection browser test passed in Edge,
including source selection and both save choices. Browser screenshots use the
component test harness, not the full application's styles. Reports are in
`.test-artifacts/run-selection/`. These checks use temporary synthetic recordings;
the revised policy has not yet been rerun through the real reference-data matrix
or a real Blender process.

### Earlier saved-stage verification (before revised run policy)

Focused verification: 88 tests and 11 subtests passed, including all six numerical
start/finish ranges, changed fit inputs, changed recording revisions, numerical
failure and cancellation before final replacement. Two longer existing saved-stage
regressions on test and sample data passed separately. TypeScript checking and the
stage-checkbox browser test passed. The complete corrected real-data matrix result
is recorded below.


### Final real-data result

All 15 contiguous test-data ranges passed after removing an inference-device
validation gate from the saved-observation route. The first attempt retained its
four failures in `fmc-sm-1013e`; the complete corrected rerun is `fmc-sm-1013f`.
No legacy fallback was used. Source videos and the selected calibration were
checked unchanged. The maximum absolute channel-value difference was
1.0231815394945443e-11, within the existing atol=1e-6, rtol=1e-8 comparison contract.
Fresh starts and saved-2D starts matched exactly. The tiny remaining differences
occurred when filtering already-aligned saved points.

| Start | Finish | Application seconds | Milliseconds per mocap frame |
| --- | --- | ---: | ---: |
| observations | observations | 24.765 | 111.55 |
| observations | triangulation | 24.885 | 112.09 |
| observations | filtering | 25.304 | 113.98 |
| observations | scale_fit | 24.688 | 111.21 |
| observations | reconstruction | 26.458 | 119.18 |
| triangulation | triangulation | 14.403 | 64.88 |
| triangulation | filtering | 13.364 | 60.20 |
| triangulation | scale_fit | 13.352 | 60.14 |
| triangulation | reconstruction | 14.119 | 63.60 |
| filtering | filtering | 2.120 | 9.55 |
| filtering | scale_fit | 2.242 | 10.10 |
| filtering | reconstruction | 5.052 | 22.76 |
| scale_fit | scale_fit | 1.979 | 8.91 |
| scale_fit | reconstruction | 4.662 | 21.00 |
| reconstruction | reconstruction | 4.697 | 21.16 |

These are single correctness runs, not a controlled performance comparison. The
report separately retains total test-case time, including copying, worker setup,
read-back validation and shutdown. Local reports: `.test-artifacts/staged-completion/`
(`report.txt`, `matrix.json`, `final-tests.log`); case files/logs are in the temporary
`fmc-sm-1013f` directory identified by the report. The matrix deliberately covers
test data, RTMPose and ChArUco with annotation, automatic alignment and a 1 Hz
filter. It does not certify all detector/device configurations, the sample-data
15-range matrix, Blender exports, or a new keep/fork policy.
