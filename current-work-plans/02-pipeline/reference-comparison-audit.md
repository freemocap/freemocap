# Extend the existing reference workflow for posthoc comparisons

Source audit, 2026-10-11, worktree baseline `d057537d`. Proposed additions only;
no datasets were processed and no application runtime changed for this audit.

## Existing machinery is the foundation

Paths below are relative to this repository. Read implementations as well as docs.

| Existing owner | Verified capability |
| --- | --- |
| `freemocap/tools/datasets/catalog.py`, `inspection.py` | Existing reference recordings and source inspection; use released data, not a new generator. |
| `freemocap/tools/datasets/__main__.py`, `workflow.py` | Explicit process/calibrate/export/validate/status/recover operations; start-stage/run/group selection; preflight and separate recording/prepared roots. |
| `freemocap/tools/datasets/preparation.py` | Separate production worker process with isolated application directory; existing registry/shared inference/manager; exact executed configuration, source hashes, actual package/core fingerprints, and result reports. |
| `freemocap/tools/datasets/storage.py`, `workflow.py` | Candidate attempts, retained logs, accepted current results, history and recoverable replacement; failures preserve previous accepted results. |
| `freemocap/tools/datasets/validation.py`, `output_acceptance.py` | Recording/channel/frame validity, alignment and stage provenance; artifact hashes and versioned output acceptance. Standard currently requires Parquet and Blender; numerical-only is explicitly incomplete relative to standard. |
| `freemocap/tools/datasets/progress.py` | Existing rate displays, stage milestones and durations, plus diagnostic table rendering. Rates derive from observed progress intervals and are not precise operation timing. |
| `freemocap/core/pipeline/performance_report.py` | Worker/coordinator timing aggregates; overlapping wall-clock intervals are explicitly non-additive. |
| `freemocap/tests/reference_recordings/` | Production-output consumers, upstream-preserving reprocessing checks, annotated-video coverage, Blender saved-scene validation, and scientific CSV/NumPy comparisons. |

`test_data` is three cameras, 222 frames at 6 fps; `sample_data` is three
cameras, 1,108 frames at 30 fps. Their filtering settings intentionally differ.
Compare each dataset against itself; do not infer speedup by comparing the two.
Full fresh workflow attempts copy inputs without the realtime observation cache.

The scientific export consumers already exercise CSV/NPY/NPZ. At this audited
revision, that does not mean every format is part of the default standard producer
profile: `required_outputs('standard')` returns Parquet and Blender. Keep required
outputs and acceptance coverage explicit as the export work evolves.

## Additions within these owners

1. Extend the existing dataset request/worker dispatch with posthoc implementation
   selection. Preserve current behavior as the default during development. Route
   the alternate choice to the new executable graph through the same production
   boundary used by the app. Leave realtime and calibration execution unchanged.
2. Add paired-comparison orchestration to the existing dataset tooling. Reuse its
   acquisition, inspection, isolated attempts, worker execution and validators.
   Give each variant a separate prepared root under a comparison directory so
   neither replaces ordinary accepted reference results. A comparison report links
   both attempt identities and validation reports; it is not another ready-marker
   format or an independent sample-data preparation system.
3. Extend existing result reports with a versioned performance section. Persist
   structured counters/timings directly from execution rather than scraping terminal
   progress. Keep the present terminal diagnostics and full processing logs.
4. Add a paired scientific-output consumer beside existing reference consumers.
   Validate each result through existing acceptance first, then compare their
   semantic keys, coverage, validity masks and values. Reuse current export checks
   to verify each exported format against its canonical data.

## Comparison contract

Pin identical source bytes, model/configuration, camera identities, stage selection,
calibration and relevant software/provider identity. For a posthoc-only comparison,
reuse one explicitly selected calibration in both attempts; independently calibrating
twice introduces another source of numerical variation. Retain separate full fresh
production acceptance runs to exercise the end-to-end workflow.

Do not use whole-file equality as numerical parity: recording paths, provenance,
timestamps and container serialization can differ. Compare canonical scientific
rows by semantic identity with explicit expected provenance differences. Require
exact coverage, schema, units and missingness agreement; define per-channel exact
or justified tolerance comparisons and report first mismatch, counts and maximum
errors. Never silently drop unmatched rows or ignore non-finite differences.
Matching one another is insufficient: both variants must independently pass the
existing scientific and output acceptance checks.

Measure preparation/copying, model setup, processing, scientific sink completion,
annotation/export completion and acceptance-validation time separately. Report
total command wall time as well. Preserve full standard acceptance even when a
focused numerical profile is used to diagnose a bottleneck.

Extend diagnostics with active operation wall time, input/resource/output-capacity
waits, batch sizes and actual providers/devices, camera and synchronized-frame
throughput, queue item/byte high-water marks, memory, and report-channel overhead.
Device timing requires separate instrumentation; call wall time is not kernel time.
Use bounded aggregates rather than unbounded per-frame event retention.

Run comparison variants sequentially, alternate order over repetitions, and record
cold/warm model state, cache reuse and other workloads. Cached accepted preparations
must not count as measured executions. Existing `compatible_identity` deliberately
allows software changes without forcing inference; comparison mode therefore needs
fresh executions even when ordinary consumer reuse would be valid. Store failures,
timeouts and incomplete measurements too; do not publish a speedup from survivors only.

## Implementation order and tests

First extend request/report contracts and tests in the existing workflow; then add
the alternate execution adapter as the graph becomes runnable. Do not create a
standalone replacement baseline runner. Add pairing/comparison tests for mismatched
inputs, missing rows, changed masks, numerical differences, invalid exports, reused
preparations and worker failure. Verify comparison runs leave normal current/history
untouched and both sides receive the same acceptance checks.

Use existing test-data processing for the first real comparison, then sample data
and saved-stage scenarios. Additional graph fault/concurrency tests complement this
workflow; they do not replace the production-generated acceptance fixtures.

No performance claim follows from this source audit. Hardware runs, actual output
comparisons and controlled repetitions are still required.
