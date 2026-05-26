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

## Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| **Crate scaffolding** | ✅ Complete | 22 source files, cargo check passes with zero errors |
| **Standalone server + PyO3 bridge** | ✅ Complete | Binary (`main.rs` + Axum), PyO3 module, shared core engine |
| **Pipeline engine** | ✅ Complete | Distributor polls FrameSlots directly, Barrier fan-out, JPEG decode, charuco detect, aggregator |
| **PipelineManager** | ✅ Complete | CRUD operations, realtime + posthoc maps, Pipeline ID ontology |
| **HTTP API** | ✅ Complete | Pipeline create/list/delete/config endpoints on port 53118 |
| **Timestamps** | ✅ Complete | Full chain: skellycam → distributor → camera node → aggregator stages |
| **Module READMEs** | ✅ Complete | Top-level + per-module docs |
| **Python adapter + Manager integration** | ✅ Complete | RustRealtimePipeline adapter, USE_RUST_BACKEND in manager |
| **Charuco triangulation** | ✅ Complete | DLT + outlier rejection + reprojection gate. Verified: 1023 points, 2.1m scale |
| **One Euro filter + velocity gate** | ✅ Complete | Adaptive low-pass + teleportation spike rejection |
| **Synchronized video reader** | ✅ Complete | `VideoGroup` — N videos, sequential read, frame count verification |
| **Tests** | ✅ Complete | 10 tests pass (DLT, calibration loader, integration, video reader, E2E pipeline) |
| Calibration → aggregator wiring | ✅ Complete | Aggregator holds calibration models, calls triangulate_charuco_corners(), feeds results into filter chain |
| **End-to-end pipeline test** | ✅ Complete | VideoGroup feeds 30 frames through full thread topology (distributor→barrier→camera nodes→aggregator) — 400 3D points at 1892mm scale |
| **Tracing logs** | ✅ Complete | TRACE/DEBUG/INFO/WARN logs throughout pipeline, SkellyFormat-compatible |
| `maturin develop` + Python import | ⬜ Next | Build .pyd, verify `import _freemocap_rust` |
| **Posthoc Pipeline** | 🔜 Next | Build proper posthoc processing pipeline around VideoGroup (multi-video reader + detection + triangulation) |
| Skeleton Inference (CPU) | 🔜 Later | Per-camera RTMPose in camera nodes |
| GPU Batched Inference | 🔜 Later | Centralized node, batched ONNX |
| Real-time server smoke test | 🔜 Later | Camera group + real-time pipeline + frontend payload |

## Upstream Changes

These were fixed in sibling crates as prerequisites:

| Crate | Change | Spec |
|-------|--------|------|
| skellycam | `RawFrame` now carries `frame_number` + `timestamps` | [spec](../skellycam-architecture/10-rawframe-metadata.md) |
| skellytracker | Bumped pyo3 0.23 → 0.28; switched to vcpkg OpenCV (x64-windows-static, +crt-static) | done |
| OpenCV | Migrated from chocolatey to vcpkg x64-windows-static triplet; unified CRT across all crates | done |

## Key Design Decisions

1. **Standalone binary + PyO3 module** — same crate, two entry points (matching skellycam's pattern). Binary boots its own Tokio runtime + Axum server on `:53118`. PyO3 cdylib loads in-process with the existing FastAPI server.
2. **Path dependencies** — `freemocap-rust` depends on sibling `skellycam-rust` and `skellytracker-rust` via `path = "..."`.
3. **Inverted BreakableBarrier** — same primitive as skellycam's camera sync, applied to fan-out (1 distributor → N camera nodes) instead of fan-in (N cameras → 1 gatherer).
4. **Frontend payload rides through** — distributor snapshots both raw frames AND the pre-encoded frontend payload in one atomic read, so the final output always pairs the correct images with the correct processed data.
5. **Manager-level backend switch** — `USE_RUST_BACKEND` flag lives in `RealtimePipelineManager`, not in individual pipeline factories. Same pattern as skellycam's `CameraGroupManager`.
