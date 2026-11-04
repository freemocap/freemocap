# SFN26 integration — November 4, 2026

The combined implementation joins UI harness a0c46a96, UI integration af266ac4,
SFN26 board detection 1fec74ce, and machine benchmarks d66b2659. Merge commits
dde00dff and 329ef092 preserve the source histories.

## Integration decisions

- Preserve requested Blender export and automatic opening, NPZ, wide CSV and notebook.
  The standard dataset workflow opens Blender after promoting its validated output
  to the final path. Opening inside the temporary worker locks promotion on Windows;
  the GUI must also have independent standard handles so worker log collection can finish.
- Keep runtime-based Blender/Python packaging and add-on-owned platform/wheel validation.
  Do not restore the obsolete version allowlist. Keep builder source in the package cache key.
- Preserve explicit provider choices and CUDA preference, then use Tracker discovery for Auto,
  including CoreML on Mac. Keep detailed stage timing and failure reports.
- Retain self-describing progress, plan identity, dependencies and final per-video counts.
- Keep both bibliography additions. No dependency checkout edits are required by the merge.

## Verification

Focused combined backend run: 129 passed, 2 failures in obsolete Blender version-rejection
expectations. Those tests were corrected to verify detected-runtime forwarding and retain
missing-platform rejection; targeted packaging/performance run: 14 passed.
Bibliography: 74 references, zero errors; 8 checker tests passed. UI SDK/typecheck passed.

A real 1,108-frame, three-camera sample through the combined UI completed all 17 operations
in 87.132 seconds. All 13 reported files exist, including .blend, .npz, .csv and .ipynb.
The actual request enabled Blender auto-open and all standard scientific exports.
RTMW and YOLOX logs confirm CoreMLExecutionProvider with CPU fallback. Tracking took
47.484 seconds. Capture reported no page errors, and the completed Graph screenshot was
inspected. The previous explicit-CPU sample took 212.865 seconds overall; these shared-desktop
runs are useful integration observations, not a controlled benchmark comparison.

Local ignored evidence is under .test-artifacts/runs/sfn26-landing and
.test-artifacts/ui-inventory/graph-sfn26-landing in the harness checkout. Portable benchmark
records and definitions are in benchmarks/README.md and benchmarks/COREML-RESULTS-2026-11-03.md.
Historical benchmark records retain their original export contract; do not relabel them as
validating the expanded standard export set.

## Outstanding work

Prior UI validation found four frozen visual snapshot failures and 44 CSS findings; baselines
and tolerances were preserved. Per-video counts exist in messages but separate item bars are
not yet rendered. These issues are not claimed fixed by this merge. The full reference matrix,
Windows hardware and frozen executable integration were not rerun for this combined state.
Benchmark camera failures remain documented in benchmarks/COMPATIBILITY-AUDIT-2026-11-03.md
and the archived camera results; no camera backend fix is claimed.

For continued UI work, read UI-REFACTOR-HANDOFF.md and UI-TEST-BASELINE.md on
sfn26-ui-refactor, then current source and this note. Older handoff instructions to disable
requested exports or reject newer Blender versions do not supersede the decisions above.
