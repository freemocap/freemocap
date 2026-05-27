# freemocap-rust

Standalone Rust server and PyO3 module for the FreeMoCap real-time motion capture pipeline.

## Status

| Component | Status |
|-----------|--------|
| Crate scaffolding | ✅ Complete |
| Pipeline engine (distributor, camera nodes, aggregator) | ✅ Complete |
| Thread spawning | ✅ Complete |
| Timestamp chain (skellycam → output) | ✅ Complete |
| PipelineManager (CRUD, lifecycle) | ✅ Complete |
| Axum HTTP API | ✅ Complete |
| PyO3 bridge | ✅ Complete |
| Charuco triangulation (DLT + outlier rejection) | ✅ Complete |
| Python adapter + Manager integration | ✅ Complete |
| Filter implementations (One Euro, velocity gate) | ⬜ Next |
| Posthoc pipeline | 🔜 Later |
| GPU batched inference | 🔜 Later |

## Architecture

```
freemocap-rust/
├── Cargo.toml              [lib] cdylib + rlib, [[bin]] freemocap-rust
└── src/
    ├── main.rs              binary: Tokio runtime, Axum server on :53118
    ├── lib.rs               module declarations + init_logging
    ├── api/                 Axum HTTP routes
    │   ├── router.rs        build_router(state)
    │   ├── routes.rs        pipeline CRUD endpoints
    │   ├── state.rs         AppState { camera_manager, pipeline_manager }
    │   └── freemocap-api-README.md
    ├── pipeline/            core engine (shared by binary + PyO3 paths)
    │   ├── distributor.rs   polls CameraGroup FrameSlots, Barrier fan-out
    │   ├── camera_node.rs   JPEG decode → charuco detection
    │   ├── aggregator.rs    fan-in, triangulation, filtering
    │   ├── types.rs         CameraNodeOutput, AggregatorOutput, etc.
    │   ├── config.rs        PipelineConfig (serde-deserializable)
    │   └── freemocap-pipeline-README.md
    ├── pipeline_manager/    pipeline lifecycle management
    │   ├── mod.rs           PipelineManager { realtime, posthoc maps }
    │   └── freemocap-pipeline-manager-README.md
    ├── filtering/           One Euro, velocity gate, skeleton filter
    ├── triangulation/       charuco DLT
    └── pyo3_bridge/         Python entry point
        ├── mod.rs           #[pymodule] fn _freemocap_rust
        ├── py_pipeline.rs   PyPipeline (wraps RealtimePipeline)
        └── freemocap-pyo3-bridge-README.md
```

## Data Flow (Zero Python in the Hot Path)

```
CameraGroup (skellycam, same process)
  dispatcher writes Arc<Mutex<Option<T>>> slots
        │
        │ Pipeline holds FrameSlots (Arc clones)
        ▼
Distributor: polls slots directly, writes DistributorSlot, Barrier.wait()
    → CameraNodes: JPEG decode, charuco detect, send to Aggregator
    → Aggregator: collect, triangulate, filter, publish AggregatorOutput
        │
        ▼
WebSocket relay (Axum) or Python polling
```

## Prerequisites

OpenCV with FFmpeg support, installed via vcpkg (static linking):

```bash
vcpkg install opencv4[ffmpeg]:x64-windows-static --recurse
```

This pulls in FFmpeg (avcodec, avformat, avutil, swscale) and rebuilds OpenCV
with `CAP_FFMPEG` enabled. The `x64-windows-static` triplet statically links
everything — no DLLs to bundle at runtime.

The `.cargo/config.toml` expects `VCPKG_ROOT=C:\tools\vcpkg` and the
`x64-windows-static` triplet. Adjust if your vcpkg is installed elsewhere.

## Install & Run

### Binary (standalone server)
```bash
cargo run
# Listens on http://0.0.0.0:53118
```

### PyO3 module (Python in-process)
```bash
maturin develop
# Then in Python: import _freemocap_rust
```

### Build check
```bash
cargo check                           # full check
cargo check --no-default-features      # rlib-only (rust-analyzer)
```

## Module READMEs

- [Pipeline engine](./src/pipeline/freemocap-pipeline-README.md) — DAG topology, threads, data types
- [Pipeline manager](./src/pipeline_manager/freemocap-pipeline-manager-README.md) — lifecycle, CRUD, ontology
- [HTTP API](./src/api/freemocap-api-README.md) — endpoints, request/response shapes
- [PyO3 bridge](./src/pyo3_bridge/freemocap-pyo3-bridge-README.md) — Python integration

## Architecture Docs

See [rearchitecture-docs/freemocap-architecture/](../rearchitecture-docs/freemocap-architecture/) for the full design methodology, invariants, and comparison with the Python implementation.
