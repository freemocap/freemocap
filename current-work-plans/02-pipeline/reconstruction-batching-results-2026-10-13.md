# Reconstruction batching results — 2026-10-13

All runs used the existing reference dataset workflow. Both routes use the current
shared scientific implementation; the comparison below measures route scheduling,
not a frozen pre-optimization executable. Isolated before/after component timings
are recorded in recording-vectorization-progress.md. Single-run measurements only.

| Dataset | Motion frames | Existing pipeline | New graph | New graph ms/motion frame | Saved parity |
|---|---:|---:|---:|---:|---|
| test_data | 222 | 42.567 s | 34.111 s | 153.65 | 36 channels, exact numeric equality |
| sample_data | 1108 | 131.225 s | 106.587 s | 96.20 | 36 channels, exact numeric equality |

One motion frame includes all three cameras. Timings include requested annotation,
Parquet and validated Blender export; CSV/NPY/NPZ exports were not requested.
The separate test-harness validation and launch overhead are not included in the
mocap timing. Worker totals including validation:
- test_data: existing 70.685 s; graph 49.596 s.
- sample_data: existing 162.466 s; graph 137.805 s.

Detector logs report requested TensorRT falling back to CUDA (with CPU also listed
as an available provider); TensorRT-specific options were ignored. These are CUDA
runs, not successful TensorRT runs. Source videos and shared calibration were kept
unchanged. Detailed configurations, logs, and channel comparisons are in:
`C:/Users/jonma/freemocap_data/testing/vbatch/comparison.json`.

Validation: 13 focused reconstruction tests, 13 backend transport tests, and one
frontend reconciliation test passed. See websocket-static-reuse-audit.md for
reuse guarantees and remaining unmeasured transport work. No SkellyForge or
SkellyTracker checkout changes were required.

This completes the current checklist; it does not claim all performance opportunities
are exhausted. Sequential temporal roll and public result-object packing remain.
GPU batching, staged-restart expansion, and transport decoding optimization are
not implemented by this change.
