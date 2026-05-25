# Crate Structure

> Step 4 (Design Rust Architecture) — directory layout, Cargo.toml, and build configuration.

## Directory Layout

```
freemocap-rust/
├── Cargo.toml
├── pyproject.toml
├── build.rs                    (if needed for OpenCV DLLs)
├── .cargo/
│   └── config.toml             OPENCV_LINK_PATHS etc.
└── src/
    ├── lib.rs                   pub mod declarations + init_logging
    ├── pipeline/
    │   ├── mod.rs
    │   ├── distributor.rs       Fan-out thread + BreakableBarrier
    │   ├── camera_node.rs       Per-camera detection thread
    │   ├── aggregator.rs        Fan-in, triangulation, filtering
    │   ├── types.rs             CameraNodeOutput, AggregatorOutput, DistributorSlot
    │   └── config.rs            PipelineConfig, CharucoDetectorConfig, FilterConfig
    ├── triangulation/
    │   ├── mod.rs
    │   └── charuco.rs           Charuco DLT triangulation
    ├── filtering/
    │   ├── mod.rs
    │   ├── one_euro.rs          One Euro filter
    │   ├── velocity_gate.rs     RealtimePointGate
    │   └── skeleton_filter.rs   FABRIK bone constraint (deferred)
    └── pyo3_bridge/
        ├── mod.rs               #[pymodule] fn _freemocap_rust
        ├── py_pipeline.rs        #[pyclass] PyPipeline
        └── types.rs             Python-facing types
```

## Cargo.toml

```toml
[package]
name = "freemocap"
version = "0.1.0"
edition = "2021"

[lib]
name = "freemocap"
crate-type = ["cdylib", "rlib"]

[features]
default = ["python-bindings"]
python-bindings = ["pyo3/extension-module"]

[dependencies]
# ── Sibling crates (path dependencies) ──
skellycam = { path = "../../skellycam/skellycam-rust" }
skellytracker = { path = "../../skellytracker/skellytracker-rust" }

# ── PyO3 ──
pyo3 = { version = "0.23" }

# ── Serialization ──
serde = { version = "1", features = ["derive"] }
serde_json = "1"

# ── Math ──
ndarray = { version = "0.17", features = ["serde"] }

# ── OpenCV (JPEG decode, triangulation) ──
opencv = "0.98"

# ── Error handling ──
anyhow = "1"
thiserror = "2"

# ── Logging ──
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
tracing-log = "0.2"
pyo3-log = "0.13"

# ── UUID ──
uuid = { version = "1", features = ["v4"] }

[build-dependencies]
# (if needed for DLL copying, etc.)

[profile.release]
opt-level = 3
lto = true
```

## pyproject.toml

```toml
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "freemocap-rust"
requires-python = ">=3.10"

[tool.maturin]
module-name = "_freemocap_rust"
```

## What Each Module Does

### `src/lib.rs`

Module declarations + logging initialization. Same pattern as skellycam:

```rust
pub mod pipeline;
pub mod triangulation;
pub mod filtering;
pub mod pyo3_bridge;

pub const DEFAULT_LOG_LEVEL: &str = "freemocap=debug,skellycam=debug,info";

pub fn init_logging(log_level: &str) {
    use tracing_subscriber::EnvFilter;
    use tracing_subscriber::layer::SubscriberExt;
    use tracing_subscriber::util::SubscriberInitExt;

    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(log_level));

    let _ = tracing_subscriber::registry()
        .with(
            tracing_subscriber::fmt::layer()
                .event_format(skellycam::logging::SkellyFormat::new())
                .with_filter(filter),
        )
        .try_init();
}
```

### `src/pipeline/mod.rs`

The `Pipeline` struct — owns all threads and channels:

```rust
pub struct Pipeline {
    camera_ids: Vec<String>,
    cmd_senders: Vec<mpsc::Sender<PipelineCommand>>,
    output_slot: Arc<Mutex<Option<AggregatorOutput>>>,
    distrib_handle: Option<JoinHandle<()>>,
    camera_handles: Vec<JoinHandle<()>>,
    aggregator_handle: Option<JoinHandle<()>>,
    barrier: Arc<BreakableBarrier>,
}

impl Pipeline {
    pub fn new(
        camera_group_manager: &skellycam::CameraGroupManager,
        config: &PipelineConfig,
        camera_ids: Vec<String>,
    ) -> Self { ... }

    pub fn start(&mut self) { ... }
    pub fn shutdown(&mut self) { ... }
}
```

### `src/triangulation/`

Pure math — no OpenCV dependency (uses nalgebra or ndarray):

```rust
pub fn triangulate_charuco_point(
    observations: &[(CameraMatrix, [f64; 2])],  // (intrinsics, 2D point)
    projection_matrices: &[Mat3x4],              // extrinsics
) -> Option<[f64; 3]> { ... }
```

### `src/filtering/`

Stateless filter implementations:

```rust
pub struct OneEuroFilter { min_cutoff: f64, beta: f64, d_cutoff: f64, ... }
impl OneEuroFilter {
    pub fn filter(&mut self, t: f64, values: &HashMap<String, [f64; 3]>) -> HashMap<String, [f64; 3]> { ... }
}

pub struct RealtimePointGate { max_velocity: f64, ... }
impl RealtimePointGate {
    pub fn gate(&mut self, t: f64, points: &HashMap<String, [f64; 3]>) -> GateResult { ... }
}
```

## Build

```bash
# In freemocap-rust/
poe rebuild          # maturin develop (editable install)
# or
maturin develop      # build + install into current venv
```

## Resolved Design Decisions

1. **`BreakableBarrier` ownership** — Depend on skellycam's (`skellycam::camera_group::sync_utils::BreakableBarrier`). It's a public, proven module. No copy needed.

2. **Calibration format** — Read the same calibration JSON format as Python's `CalibrationStateTracker`. File path passed from Python at pipeline construction time. Hot-reload via `fs::metadata` polling.

3. **ndarray vs nalgebra** — Use `ndarray 0.17` for consistency with skellytracker. It's already in the dependency tree and handles OpenCV interop.

4. **Timing infrastructure** — Add `FrameLifecycleTimestamps` from day one. Reuse skellycam's `timestamps::performance::performance_counter_nanoseconds()` for T=0-anchored monotonic timestamps. Five timestamps per camera node cycle: `loop_start_ns`, `dequeue_frame_ns`, `post_jpeg_decode_ns`, `post_detection_ns`, `pre_send_ns`.

## Open Investigation (implementation phase)

- **Calibration file path convention** — confirm the exact path and JSON schema during implementation. Approached via reading the Python `CalibrationStateTracker` source.
- **Python Pydantic ↔ Rust serde JSON shape** — verify the exact field names. The JSON is the contract.
