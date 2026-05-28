# FreeMoCap Rust — Architecture Documentation

> Apply the [re-architecture playbook](../rearchitecture-playbook/) to the FreeMoCap real-time pipeline, composing skellycam-rust (cameras) and skellytracker-rust (detection).

## Documents

| # | Document | Component |
|---|----------|-----------|
| 01 | [System Overview & Integration](./01-system-overview.md) | Crate integration, process model, dependencies |
| 02 | [Pipeline Topology](./02-pipeline-topology.md) | DAG structure, thread model, data flow |
| 03 | [Distributor & Frame Sync](./03-distributor-frame-sync.md) | BreakableBarrier fan-out, latest-frame polling, frontend payload bundling |
| 04 | [Camera Nodes](./04-camera-nodes.md) | JPEG decode, charuco detection, per-camera threads |
| 05 | [Aggregator](./05-aggregator.md) | Fan-in collection, triangulation, filtering, output publishing |
| 06 | [Channel Architecture](./06-channel-architecture.md) | mpsc channels, command dispatch, `try_recv` pattern |
| 07 | [Config Handling](./07-config-handling.md) | Real-time config updates, serde deserialization, hot-swappable backend |
| 08 | [PyO3 Bridge](./08-pyo3-bridge.md) | Module layout, pyclass wrappers, Python adapter |
| 09 | [Crate Structure](./09-crate-structure.md) | Directory layout, Cargo.toml, path dependencies |
| 10 | [Implementation Plan](./10-implementation-plan.md) | Step-by-step build plan with code |
| 11 | [RealtimeEngine Abstraction](./11-realtime-engine-abstraction.md) | Unified camera + pipeline interface, Python/Rust swap via module-level constant |

## Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| **Crate scaffolding** | ✅ Complete | 22 source files, cargo check passes with zero errors |
| **Standalone server + PyO3 bridge** | ✅ Complete | Binary (`main.rs` + Axum), PyO3 module, shared core engine |
| **Pipeline engine** | ✅ Complete | Distributor supports both FrameSlots (camera) and mpsc channel (video); Barrier fan-out; JPEG decode; charuco detect; aggregator |
| **PipelineManager** | ✅ Complete | CRUD operations, realtime + posthoc maps, Pipeline ID ontology |
| **HTTP API** | ✅ Complete | Pipeline create/list/delete/config endpoints on port 53118 |
| **Composable timestamps** | ✅ Complete | `DistributorTimestamps` + `CameraNodeTimestamps` + `AggregatorTimestamps` → composite `PipelineCycleTimestamps`; every loop gets its own struct with duration helpers |
| **Pipeline timing statistics** | ✅ Complete | Per-stage, per-camera stats block (median/mean/std/CV%/min/max/n) matching skellycam gatherer format |
| **Module docs** | ✅ Complete | Top-level lib.rs + per-module doc strings |
| **Python adapter + Manager integration** | ✅ Complete | RustRealtimePipeline adapter, USE_RUST_BACKEND in freemocap_application.py |
| **Charuco triangulation** | ✅ Complete | DLT + outlier rejection + reprojection gate. Verified: 1023 points, 2.1m scale |
| **One Euro filter + velocity gate** | ✅ Complete | Adaptive low-pass + teleportation spike rejection |
| **VideoGroup (first-class)** | ✅ Complete | `VideoReader` + dispatcher thread + unbounded mpsc channel → `MultiFramePayload`; lifecycle: open→start→shutdown; 11 tests pass |
| **Tests** | ✅ Complete | 11 tests pass (DLT, calibration loader, integration, video reader, E2E pipeline) |
| Calibration → aggregator wiring | ✅ Complete | Aggregator holds calibration models, calls `triangulate_charuco_corners()`, feeds results into filter chain |
| **End-to-end pipeline test** | ✅ Complete | VideoGroup feeds 30 frames → 397 3D points, **36.9 fps** (release) |
| **Tracing logs** | ✅ Complete | TRACE/DEBUG/INFO/WARN logs throughout pipeline, SkellyFormat-compatible |
| **Video read performance** | ✅ Complete | CAP_FFMPEG backend: 33ms → 3.5ms per 3 frames (9.4×) |
| **JPEG encode optimization** | ✅ Complete | Quality 95: encode 12ms → 8ms, decode 5ms → 3ms |
| **Single-call charuco detect** | ✅ Complete | detect_board handles markers+charuco in one C++ call (matches Python) |
| `maturin develop` + Python import | ⬜ Next | Build .pyd, verify `import _freemocap_rust` |
| **PyO3 bridge — stats + calibration** | ✅ Complete | PyPipeline collects per-thread stats (printed on shutdown), calibration TOML loaded by Rust from path |
| **PyO3 bridge — `get_latest_output()`** | ✅ Complete | Returns keypoints_raw, keypoints_filtered, camera_observations (charuco corner IDs + coords) |
| **Test CLI** | ✅ Complete | clap-based CLI following skellycam pattern: `cargo run -- test {all,detect,pipeline,calibration,charuco,video,filtering}` |
| **PythonRealtimeEngine** (refactor) | ✅ Complete | CameraGroupManager + RealtimePipelineManager wrapped as private internals behind unified RealtimeEngine interface |
| **PyRealtimeEngine** (Rust PyO3) | ✅ Complete | Single `#[pyclass]` bundling camera management + pipeline threads; `result_ready` signaling for websocket relay |
| **RustRealtimeEngine adapter** | ✅ Complete | Thin Python wrapper around `_freemocap_rust.RealtimeEngine`, matching PythonRealtimeEngine interface |
| **USE_RUST_BACKEND swap** | ✅ Complete | Module-level bool in freemocap_application.py, swaps between Python/Rust implementations at construction time |
| **Frontend smoke test** | ⬜ Next | Human test: connect frontend, verify camera feed + charuco overlay + triangulated 3D keypoints |
| **Posthoc Pipeline** | 🔜 Next | VideoGroup + channel infrastructure ready; next: posthoc processing mode, result export |
| Skeleton Inference (CPU) | 🔜 Later | Per-camera RTMPose in camera nodes |
| GPU Batched Inference | 🔜 Later | Centralized node, batched ONNX |
| Real-time server smoke test | 🔜 Later | Camera group + real-time pipeline + frontend payload |

## Upstream Changes

These were fixed in sibling crates as prerequisites:

| Crate | Change | Spec |
|-------|--------|------|
| skellycam | `RawFrame` now carries `frame_number` + `timestamps` | [spec](../skellycam-architecture/10-rawframe-metadata.md) |
| skellycam | `MultiFramePayload` wraps `GathererTimestamps` instead of bare `i64` fields | composable timestamp consistency |
| skellytracker | Bumped pyo3 0.23 → 0.28; single-call detect_board (removed per-frame ArucoDetector allocs) | done |
| OpenCV | Migrated from chocolatey to vcpkg x64-windows-static with ffmpeg feature; unified CRT | done |

## Key Design Decisions

1. **Standalone binary + PyO3 module** — same crate, two entry points (matching skellycam's pattern). Binary boots its own Tokio runtime + Axum server on `:53118`. PyO3 cdylib loads in-process with the existing FastAPI server.
2. **Path dependencies** — `freemocap-rust` depends on sibling `skellycam-rust` and `skellytracker-rust` via `path = "..."`.
3. **Inverted BreakableBarrier** — same primitive as skellycam's camera sync, applied to fan-out (1 distributor → N camera nodes) instead of fan-in (N cameras → 1 gatherer).
4. **Dual-source distributor** — distributor checks `video_rx.is_some()`: if Some, uses `recv()` on mpsc channel (video path); if None, polls `FrameSlots` (live camera path). Same `DistributorSlot` output either way.
5. **Composable per-loop timestamps** — every thread loop gets its own `Timestamps` struct with named stage boundaries. `PipelineCycleTimestamps` composes `DistributorTimestamps` + `HashMap<String, CameraNodeTimestamps>` + `AggregatorTimestamps`. Duration helpers (`slot_work_ns()`, `triangulation_ns()`) compute `end − start` inline.
6. **VideoGroup uses MultiFramePayload channel** — video dispatcher sends skellycam's `MultiFramePayload` on an unbounded mpsc channel. Natural backpressure via `recv()` blocking. No FrameSlots, no pacing signal, no spin-waits for video sources.
7. **Frontend payload rides through** — distributor snapshots both raw frames AND the pre-encoded frontend payload in one atomic read, so the final output always pairs the correct images with the correct processed data.
8. **Engine-level backend switch** — `USE_RUST_BACKEND` flag lives in `freemocap_application.py`. `FreemocapApplication.create()` picks `PythonRealtimeEngine` or `RustRealtimeEngine` at construction time. The managers (`CameraGroupManager`, `RealtimePipelineManager`) are private implementation details inside `PythonRealtimeEngine` — no external code accesses them directly.
9. **Single-call charuco detection** — `detect_board()` is called with empty marker containers, letting OpenCV handle marker detection + charuco interpolation in one C++ call. Matches Python's `detectBoard()` exactly. No per-frame `ArucoDetector` allocations.
10. **JPEG quality 95 for posthoc** — the video dispatcher encodes BGR frames at quality 95 (not 100). The ~1% pixel difference is below charuco detection threshold, but encode time nearly halves.
11. **FFmpeg for video read** — `CAP_FFMPEG` instead of `CAP_ANY` avoids Windows MSMF overhead. Requires `opencv4[ffmpeg]:x64-windows-static` from vcpkg.
