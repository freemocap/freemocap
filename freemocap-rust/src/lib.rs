//! FreeMoCap Rust crate — real-time and posthoc multi-camera processing.
//!
//! # Module Map
//!
//! | Module | Purpose |
//! |--------|---------|
//! | `pipeline` | Real-time pipeline engine (distributor, camera nodes, aggregator) |
//! | `pipeline::types` | Composable per-loop timestamps (`DistributorTimestamps`, `CameraNodeTimestamps`, `AggregatorTimestamps`, `PipelineCycleTimestamps`) |
//! | `pipeline::stats` | Per-stage, per-camera timing statistics (skellycam gatherer-format output) |
//! | `pipeline_manager` | Lifecycle management for real-time and posthoc pipelines |
//! | `triangulation` | DLT triangulation, charuco corner grouping, outlier rejection, calibration loading |
//! | `filtering` | One Euro filter, velocity gate, skeleton filter (stub) |
//! | `video_reader` | Synchronized multi-video playback via `VideoGroup` + unbounded mpsc channel |
//! | `pyo3_bridge` | PyO3 wrappers for Python integration |
//! | `api` | Axum HTTP server (standalone binary entry point) |
//!
//! # Key Architecture Decisions
//!
//! - **Composable timestamps**: Every loop gets its own `Timestamps` struct.
//!   `PipelineCycleTimestamps` composes `DistributorTimestamps` +
//!   `HashMap<String, CameraNodeTimestamps>` + `AggregatorTimestamps`.
//! - **VideoGroup uses mpsc channel**: The video dispatcher sends `MultiFramePayload`
//!   (skellycam's type) on an unbounded channel. The distributor receives via
//!   `recv()` — no FrameSlots polling for video sources.
//! - **Camera source still uses FrameSlots**: When connected to live CameraGroup,
//!   the distributor polls `FrameSlots` (Arc<Mutex<Option<T>>>) via the existing
//!   real-time path. The distributor checks `video_rx.is_some()` to decide.
//! - **Upstream: skellycam `MultiFramePayload` wraps `GathererTimestamps`**:
//!   The three bare `i64` fields were replaced with a single
//!   `gatherer_timestamps: GathererTimestamps` field for consistency.

pub mod api;
pub mod pipeline;
pub mod pipeline_manager;
pub mod triangulation;
pub mod filtering;
pub mod pyo3_bridge;
pub mod video_reader;

/// Default log level for the entire process.
/// `RUST_LOG` env var overrides this if set.
pub const DEFAULT_LOG_LEVEL: &str = "freemocap=debug,skellycam=debug,info";

/// Initialize the global tracing subscriber.
///
/// Delegates to skellycam's subscriber setup which includes `SkellyFormat`
/// for consistent pipe-delimited terminal output. Idempotent — subsequent
/// calls are no-ops.
pub fn init_logging(log_level: &str) {
    skellycam::init_logging(log_level);
}
