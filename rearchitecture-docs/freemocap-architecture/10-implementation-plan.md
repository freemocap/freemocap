# FreeMoCap Rust — Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Tasks are ordered by dependency — work through them sequentially.

**Goal:** Scaffold the freemocap-rust crate, build the pipeline engine, and integrate with the Python application. ✅ COMPLETE.

**Architecture:** Standalone binary + PyO3 module (matching skellycam's pattern). Pipeline engine (distributor, camera nodes, aggregator) is pure Rust shared by both paths. Frame data flows Rust-to-Rust via `FrameSlots`. Python adapter (`RustRealtimePipeline`) and manager backend flag (`USE_RUST_BACKEND`) complete.

**Tech Stack:** Rust edition 2024, PyO3 0.28, ndarray 0.17, opencv 0.98, serde/serde_json, tokio + axum for binary. Maturin for build.

**Source of truth:** [freemocap-architecture docs](./README.md) — this plan implements the design described in documents 01-09.

**Next milestone:** Triangulation + filtering (real One Euro, velocity gate, charuco DLT).


---

### Task 1: Create Cargo.toml

**Files:**
- Create: `freemocap-rust/Cargo.toml`

The crate depends on skellycam-rust and skellytracker-rust via relative path dependencies. Edition 2021 (matching skellytracker — skellycam uses 2024 but that requires a newer toolchain). PyO3 with `python-bindings` feature gate matching both sibling crates.

- [ ] **Step 1: Write Cargo.toml**

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
# ── Sibling crates ──
skellycam = { path = "../../skellycam/skellycam-rust" }
skellytracker = { path = "../../skellytracker/skellytracker-rust" }

# ── PyO3 ──
pyo3 = "0.23"

# ── Serialization ──
serde = { version = "1", features = ["derive"] }
serde_json = "1"

# ── Math (match skellytracker version) ──
ndarray = "0.17"

# ── OpenCV (JPEG decode in camera nodes) ──
opencv = "0.98"

# ── Error handling ──
anyhow = "1"
thiserror = "2"

# ── Logging ──
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }

# ── UUID ──
uuid = { version = "1", features = ["v4"] }

[profile.release]
opt-level = 3
lto = true
```

- [ ] **Step 2: Verify Cargo.toml parses**

Run: `cargo metadata --manifest-path freemocap-rust/Cargo.toml --no-deps 2>&1`
Expected: No errors. May warn about unused deps — that's fine at this stage.

---

### Task 2: Create pyproject.toml for Maturin

**Files:**
- Create: `freemocap-rust/pyproject.toml`

Matches skellycam and skellytracker's maturin configuration. No `python-source` — the `.pyd` installs directly as `_freemocap_rust`.

- [ ] **Step 1: Write pyproject.toml**

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

---

### Task 3: Create .cargo/config.toml

**Files:**
- Create: `freemocap-rust/.cargo/config.toml`

Copy the OpenCV link paths from skellytracker-rust's config. This is required for the opencv crate to find OpenCV DLLs at build time.

- [ ] **Step 1: Read skellytracker's config as template**

Read: `../../skellytracker/skellytracker-rust/.cargo/config.toml`

- [ ] **Step 2: Write matching .cargo/config.toml**

Copy the exact content from skellytracker's config — same OpenCV paths, same settings. The file contents will be identical since both crates target the same OpenCV installation.

---

### Task 4: Create src/lib.rs with Module Declarations and Logging

**Files:**
- Create: `freemocap-rust/src/lib.rs`

Module declarations for all submodules plus `init_logging()` that delegates to skellycam's global tracing subscriber. The function is idempotent — if skellycam already called it, the second call is a no-op.

- [ ] **Step 1: Write src/lib.rs**

```rust
pub mod pipeline;
pub mod triangulation;
pub mod filtering;
pub mod pyo3_bridge;

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
```

- [ ] **Step 2: Verify it compiles (will fail due to missing modules — expected)**

Run: `cargo check --manifest-path freemocap-rust/Cargo.toml 2>&1`
Expected: Errors about missing modules `pipeline`, `triangulation`, `filtering`, `pyo3_bridge`. Confirms the crate can find skellycam and skellytracker deps.

---

### Task 5: Create pipeline/types.rs — Shared Data Types

**Files:**
- Create: `freemocap-rust/src/pipeline/types.rs`

Core data types that flow through the pipeline DAG. All are `Send + Sync` so they can cross thread boundaries.

- [ ] **Step 1: Write src/pipeline/types.rs**

```rust
use serde::{Deserialize, Serialize};

/// Output from a single camera node after detection.
#[derive(Debug, Clone)]
pub struct CameraNodeOutput {
    pub camera_id: String,
    pub frame_number: i64,
    /// Charuco detection result. Boxed because CharucoObservation is large
    /// (contains Vecs of corners, IDs, etc.).
    pub charuco_observation: Option<Box<skellytracker::trackers::charuco::observation::CharucoObservation>>,
}

/// Aggregated output for one multiframe cycle. Stored in a shared slot
/// for the Python websocket relay to poll.
#[derive(Debug, Clone)]
pub struct AggregatorOutput {
    pub frame_number: i64,
    /// Per-camera detection outputs (for charuco overlay data).
    pub camera_outputs: Vec<CameraNodeOutput>,
    /// Raw triangulated keypoints: point_name → [x, y, z].
    pub keypoints_raw: std::collections::HashMap<String, [f64; 3]>,
    /// Filtered keypoints after velocity gate + One Euro filter.
    pub keypoints_filtered: std::collections::HashMap<String, [f64; 3]>,
    /// The pre-encoded frontend payload captured by the distributor.
    /// Carried through the pipeline so the final output is self-consistent
    /// (images + keypoints from the same frame).
    pub frontend_payload_bytes: Vec<u8>,
    /// Multiframe timestamp from skellycam's payload.
    pub timestamp_ns: f64,
    /// True camera FPS from skellycam's framerate tracker.
    pub camera_fps: f64,
}

/// Data written by the distributor and read by all camera nodes.
/// Protected by `Arc<RwLock<DistributorSlot>>` with a BreakableBarrier
/// ensuring all cameras read the same version.
#[derive(Debug, Clone)]
pub struct DistributorSlot {
    pub frame_number: i64,
    /// Per-camera data: (camera_id, jpeg_bytes, timestamps).
    /// Timestamps are nanoseconds since T=0 from skellycam's performance clock.
    pub per_camera_data: Vec<PerCameraFrameData>,
    /// Pre-encoded frontend payload — bundled at capture time.
    pub frontend_payload_bytes: Vec<u8>,
    pub timestamp_ns: f64,
    pub camera_fps: f64,
}

/// Complete per-camera frame data for one multiframe cycle.
#[derive(Debug, Clone)]
pub struct PerCameraFrameData {
    pub camera_id: String,
    pub jpeg_bytes: Vec<u8>,
    /// skellycam FrameLifecycleTimestamps: loop_start, frame_available,
    /// post_jpeg_extract, pre_send, gatherer_received (all ns since T=0).
    pub timestamps: skellycam::camera::types::FrameLifecycleTimestamps,
}
```

- [ ] **Step 2: Create the pipeline module directory and mod.rs placeholder**

```bash
mkdir -p freemocap-rust/src/pipeline
```

Create `freemocap-rust/src/pipeline/mod.rs` with just:
```rust
pub mod types;
```

---

### Task 6: Create pipeline/config.rs — Configuration Types

**Files:**
- Create: `freemocap-rust/src/pipeline/config.rs`
- Modify: `freemocap-rust/src/pipeline/mod.rs`

Serde-deserializable config that Python passes as JSON. Charuco detector params map directly to `skellytracker::CharucoTracker::new()` arguments.

- [ ] **Step 1: Write src/pipeline/config.rs**

```rust
use serde::{Deserialize, Serialize};

/// Top-level pipeline configuration. Deserialized from Python JSON
/// (Pydantic RealtimePipelineConfig.model_dump_json()).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PipelineConfig {
    pub charuco_config: CharucoDetectorConfig,
    pub triangulation_enabled: bool,
    pub filter_config: FilterConfig,
    pub skeleton_enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CharucoDetectorConfig {
    pub squares_x: u32,
    pub squares_y: u32,
    pub square_length_mm: f32,
    pub marker_length_ratio: f32,
    pub dictionary_enum: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FilterConfig {
    pub filter_enabled: bool,
    pub min_cutoff: f64,
    pub beta: f64,
    pub d_cutoff: f64,
    pub max_velocity_m_per_s: f64,
    pub max_reprojection_error_px: f64,
    pub max_rejected_streak: u32,
    pub skeleton_enabled: bool,
}

impl Default for PipelineConfig {
    fn default() -> Self {
        Self {
            charuco_config: CharucoDetectorConfig {
                squares_x: 5,
                squares_y: 7,
                square_length_mm: 30.0,
                marker_length_ratio: 0.75,
                dictionary_enum: 2, // DICT_4X4_250
            },
            triangulation_enabled: false,
            filter_config: FilterConfig {
                filter_enabled: true,
                min_cutoff: 1.0,
                beta: 0.01,
                d_cutoff: 1.0,
                max_velocity_m_per_s: 3.0,
                max_reprojection_error_px: 5.0,
                max_rejected_streak: 5,
                skeleton_enabled: false,
            },
            skeleton_enabled: false,
        }
    }
}
```

- [ ] **Step 2: Update src/pipeline/mod.rs**

```rust
pub mod config;
pub mod types;
```

---

### Task 7: Create pipeline/distributor.rs — Frame Fan-Out Thread

**Files:**
- Create: `freemocap-rust/src/pipeline/distributor.rs`
- Modify: `freemocap-rust/src/pipeline/mod.rs`

The distributor's public interface is the `Distributor` struct (holds the barrier and command channel) and the `run_distributor` free function (the thread's main loop). The thread polls skellycam's `latest_raw_frames` and `latest_frontend_payload` slots, snapshots them atomically, writes to the shared distributor slot, and releases camera nodes via `BreakableBarrier`.

- [ ] **Step 1: Write src/pipeline/distributor.rs**

```rust
use std::sync::{Arc, RwLock, atomic::{AtomicBool, Ordering}};
use std::sync::mpsc::{self, Receiver};
use skellycam::camera_group::sync_utils::BreakableBarrier;
use skellycam::CameraGroupManager;
use super::types::{DistributorSlot, PerCameraFrameData};
use super::config::PipelineConfig;

/// Commands the distributor can receive from the pipeline manager.
#[derive(Debug, Clone)]
pub enum PipelineCommand {
    UpdateConfig(PipelineConfig),
    Shutdown,
}

/// State owned by the distributor thread.
pub struct Distributor {
    /// Barrier with count = N_cameras + 1. Distributor participates.
    pub barrier: Arc<BreakableBarrier>,
    /// Slot written by distributor, read by all camera nodes.
    pub slot: Arc<RwLock<DistributorSlot>>,
    /// Command receiver — config updates and shutdown.
    pub cmd_rx: Receiver<PipelineCommand>,
    /// Shutdown flag — set by main thread on drop.
    pub shutdown_flag: Arc<AtomicBool>,
}

impl Distributor {
    pub fn new(
        barrier: Arc<BreakableBarrier>,
        slot: Arc<RwLock<DistributorSlot>>,
        cmd_rx: Receiver<PipelineCommand>,
        shutdown_flag: Arc<AtomicBool>,
    ) -> Self {
        Self { barrier, slot, cmd_rx, shutdown_flag }
    }
}

/// Main loop for the distributor thread.
///
/// Polls skellycam's latest_raw_frames and latest_frontend_payload slots.
/// When a new frame is available (and the frontend payload matches),
/// writes the distributor slot and releases camera nodes via the barrier.
pub fn run_distributor(
    camera_group_manager: &CameraGroupManager,
    group_id: &str,
    distributor: Distributor,
) {
    let mut last_distributed: i64 = -1;

    loop {
        // ── Handle commands ──
        match distributor.cmd_rx.try_recv() {
            Ok(PipelineCommand::Shutdown) => break,
            Ok(PipelineCommand::UpdateConfig(_config)) => {
                // Config applied in next cycle.
                // Camera count changes handled via barrier.set_total().
            }
            Err(mpsc::TryRecvError::Empty) => {}
            Err(mpsc::TryRecvError::Disconnected) => break,
        }

        if distributor.shutdown_flag.load(Ordering::Relaxed) {
            break;
        }

        // ── Poll skellycam slots ──
        let group = match camera_group_manager.get_group(group_id) {
            Some(g) => g,
            None => {
                tracing::warn!("[freemocap::distributor] CameraGroup '{}' not found", group_id);
                std::thread::sleep(std::time::Duration::from_millis(10));
                continue;
            }
        };

        let raw_frames = match group.latest_raw_frames() {
            Some(frames) => frames,
            None => {
                std::thread::sleep(std::time::Duration::from_millis(1));
                continue;
            }
        };

        let frontend_payload = match group.latest_frontend_payload() {
            Some(payload) => payload,
            None => {
                std::thread::sleep(std::time::Duration::from_millis(1));
                continue;
            }
        };

        // ── Guard: slots must be populated ──
        if raw_frames.is_empty() {
            continue;
        }
        // frame_number from RawFrame (added via skellycam metadata enhancement)
        let frame_number = raw_frames[0].frame_number;
        // Verify skellycam's FrontendPayload matches (sanity check)
        if frame_number != frontend_payload.frame_number {
            tracing::error!(
                "[freemocap::distributor] frame_number mismatch: raw={} payload={}",
                frame_number, frontend_payload.frame_number
            );
            continue;
        }

        if frame_number <= last_distributed {
            // No new frame. Brief sleep to avoid busy-spinning.
            std::thread::sleep(std::time::Duration::from_millis(1));
            continue;
        }

        // ── Write shared slot ──
        {
            let mut slot = distributor.slot.write().unwrap();
            slot.frame_number = frame_number;
            slot.timestamp_ns = frontend_payload.timestamp_ns;
            slot.camera_fps = frontend_payload.camera_fps;
            slot.frontend_payload_bytes = frontend_payload.jpeg_bytes.clone();
            slot.per_camera_data = raw_frames.iter().map(|rf| {
                PerCameraFrameData {
                    camera_id: rf.camera_id.clone(),
                    jpeg_bytes: rf.jpeg_bytes.to_vec(),
                    timestamps: rf.timestamps.clone(),
                }
            }).collect();
        }

        // ── Release camera nodes ──
        if !distributor.barrier.wait() {
            break; // barrier broken (shutdown)
        }

        last_distributed = frame_number;
    }

    // Release any camera nodes still waiting at the barrier.
    distributor.barrier.break_barrier();
}
```

- [ ] **Step 2: Verify RawFrame has frame_number and timestamps**

`RawFrame` was enhanced with `frame_number: i64` and `timestamps: FrameLifecycleTimestamps` per the skellycam spec [10-rawframe-metadata](../skellycam-architecture/10-rawframe-metadata.md). Verify these fields exist before proceeding. `jpeg_bytes` is `Arc<[u8]>` — `.to_vec()` for owned copies.

- [ ] **Step 3: Update src/pipeline/mod.rs**

```rust
pub mod config;
pub mod distributor;
pub mod types;
```

---

### Task 8: Create pipeline/camera_node.rs — Per-Camera Detection Thread

**Files:**
- Create: `freemocap-rust/src/pipeline/camera_node.rs`
- Modify: `freemocap-rust/src/pipeline/mod.rs`

Each camera node is a `std::thread` running `run_camera_node()`. It blocks on the `BreakableBarrier`, reads its frame from the shared distributor slot, decodes JPEG → BGR via OpenCV, runs charuco detection via skellytracker's `CharucoTracker`, and sends the output to the aggregator.

- [ ] **Step 1: Write src/pipeline/camera_node.rs**

```rust
use std::sync::{Arc, RwLock, atomic::{AtomicBool, Ordering}};
use std::sync::mpsc::{self, Receiver, Sender};
use opencv::{imgcodecs, prelude::*};
use skellycam::camera_group::sync_utils::BreakableBarrier;
use skellycam::timestamps::performance::performance_counter_nanoseconds;
use skellytracker::trackers::charuco::CharucoTracker;
use super::types::{CameraNodeOutput, DistributorSlot};
use super::config::PipelineConfig;
use super::distributor::PipelineCommand;

/// State for a single camera node thread.
pub struct CameraNode {
    pub camera_id: String,
    pub cmd_rx: Receiver<PipelineCommand>,
    pub output_tx: Sender<CameraNodeOutput>,
    pub barrier: Arc<BreakableBarrier>,
    pub slot: Arc<RwLock<DistributorSlot>>,
    pub shutdown_flag: Arc<AtomicBool>,
}

/// Main loop for a camera node thread.
///
/// Each cycle:
/// 1. Check for commands (config update, shutdown)
/// 2. Wait at barrier (distributor has written new frame)
/// 3. Read this camera's JPEG from the shared slot
/// 4. Decode JPEG → BGR
/// 5. Run charuco detection
/// 6. Send CameraNodeOutput to aggregator
pub fn run_camera_node(node: CameraNode, mut detector: CharucoTracker) {
    loop {
        // ── Handle commands ──
        match node.cmd_rx.try_recv() {
            Ok(PipelineCommand::Shutdown) => break,
            Ok(PipelineCommand::UpdateConfig(config)) => {
                if let Ok(new_detector) = CharucoTracker::new(
                    config.charuco_config.squares_x,
                    config.charuco_config.squares_y,
                    config.charuco_config.square_length_mm,
                    config.charuco_config.marker_length_ratio,
                    config.charuco_config.dictionary_enum,
                ) {
                    detector = new_detector;
                }
            }
            Err(mpsc::TryRecvError::Empty) => {}
            Err(mpsc::TryRecvError::Disconnected) => break,
        }

        if node.shutdown_flag.load(Ordering::Relaxed) {
            break;
        }

        // ── Sync with distributor ──
        if !node.barrier.wait() {
            break; // barrier broken
        }

        // ── Read frame from shared slot ──
        let (frame_number, jpeg_bytes) = {
            let slot = node.slot.read().unwrap();
            let frame_data = slot.per_camera_data.iter()
                .find(|d| d.camera_id == node.camera_id)
                .cloned();
            match frame_data {
                Some(data) => (slot.frame_number, data.jpeg_bytes),
                None => {
                    eprintln!("[freemocap] CameraNode[{}]: no frame data in slot", node.camera_id);
                    continue;
                }
            }
        };

        let loop_start_ns = performance_counter_nanoseconds();

        // ── Decode JPEG → BGR ──
        let image = match imgcodecs::imdecode(
            &opencv::core::Vector::<u8>::from_iter(jpeg_bytes.iter().copied()),
            imgcodecs::IMREAD_COLOR,
        ) {
            Ok(img) => img,
            Err(e) => {
                eprintln!("[freemocap] CameraNode[{}]: JPEG decode error: {:?}", node.camera_id, e);
                continue;
            }
        };

        let post_jpeg_decode_ns = performance_counter_nanoseconds();

        // ── Charuco detection ──
        let observation = detector.detect(frame_number as u64, &image);
        let post_detection_ns = performance_counter_nanoseconds();

        // ── Send downstream ──
        let output = CameraNodeOutput {
            camera_id: node.camera_id.clone(),
            frame_number,
            charuco_observation: Some(Box::new(observation)),
        };

        if node.output_tx.send(output).is_err() {
            break; // aggregator disconnected
        }
    }
}
```

- [ ] **Step 2: Update src/pipeline/mod.rs**

```rust
pub mod camera_node;
pub mod config;
pub mod distributor;
pub mod types;
```

---

### Task 9: Create pipeline/aggregator.rs — Fan-In and Triangulation Thread

**Files:**
- Create: `freemocap-rust/src/pipeline/aggregator.rs`
- Modify: `freemocap-rust/src/pipeline/mod.rs`

The aggregator collects `CameraNodeOutput`s from all camera channels, verifies frame_number consistency, runs charuco triangulation (if calibrated), applies velocity gate + One Euro filter, and publishes the `AggregatorOutput` to the shared slot.

- [ ] **Step 1: Write src/pipeline/aggregator.rs**

```rust
use std::collections::HashMap;
use std::sync::{Arc, Mutex, atomic::{AtomicBool, Ordering}};
use std::sync::mpsc::{self, Receiver, Sender};
use super::types::{AggregatorOutput, CameraNodeOutput};
use super::config::{PipelineConfig, FilterConfig};
use super::distributor::PipelineCommand;

/// State for the aggregator thread.
pub struct Aggregator {
    /// Per-camera input channels — one per camera node.
    pub camera_rxs: Vec<(String, Receiver<CameraNodeOutput>)>,
    pub cmd_rx: Receiver<PipelineCommand>,
    /// Output slot polled by Python websocket relay.
    pub output_slot: Arc<Mutex<Option<AggregatorOutput>>>,
    pub shutdown_flag: Arc<AtomicBool>,
    pub camera_ids: Vec<String>,
}

pub fn run_aggregator(mut agg: Aggregator) {
    let mut config = PipelineConfig::default();
    let mut keypoint_filter = OneEuroFilter::new(
        config.filter_config.min_cutoff,
        config.filter_config.beta,
        config.filter_config.d_cutoff,
    );
    let mut velocity_gate = RealtimePointGate::new(
        config.filter_config.max_velocity_m_per_s,
        config.filter_config.max_rejected_streak,
    );

    loop {
        // ── Handle commands ──
        match agg.cmd_rx.try_recv() {
            Ok(PipelineCommand::Shutdown) => break,
            Ok(PipelineCommand::UpdateConfig(new_config)) => {
                keypoint_filter.set_params(
                    new_config.filter_config.min_cutoff,
                    new_config.filter_config.beta,
                    new_config.filter_config.d_cutoff,
                );
                velocity_gate.set_max_velocity(new_config.filter_config.max_velocity_m_per_s);
                velocity_gate.set_max_streak(new_config.filter_config.max_rejected_streak);
                config = new_config;
            }
            Err(mpsc::TryRecvError::Empty) => {}
            Err(mpsc::TryRecvError::Disconnected) => break,
        }

        if agg.shutdown_flag.load(Ordering::Relaxed) {
            break;
        }

        // ── Collect outputs from all camera nodes ──
        let mut camera_outputs: Vec<CameraNodeOutput> = Vec::with_capacity(agg.camera_rxs.len());
        let mut expected_frame: Option<i64> = None;

        for (_cam_id, rx) in &agg.camera_rxs {
            match rx.recv() {
                Ok(output) => {
                    if let Some(ef) = expected_frame {
                        if output.frame_number != ef {
                            eprintln!(
                                "[freemocap::aggregator] Frame mismatch: expected {} got {}",
                                ef, output.frame_number
                            );
                            camera_outputs.clear();
                            break;
                        }
                    } else {
                        expected_frame = Some(output.frame_number);
                    }
                    camera_outputs.push(output);
                }
                Err(_) => {
                    // Camera node disconnected — shutdown
                    camera_outputs.clear();
                    break;
                }
            }
        }

        if camera_outputs.len() != agg.camera_rxs.len() {
            break;
        }

        let frame_number = expected_frame.unwrap();

        // ── Triangulate charuco observations ──
        let mut raw_keypoints: HashMap<String, [f64; 3]> = HashMap::new();
        // TODO: Call triangulation when calibration is available.
        // For now, raw_keypoints stays empty (triangulation deferred).

        // ── Velocity gate ──
        let gated = if config.filter_config.filter_enabled {
            velocity_gate.gate(&raw_keypoints)
        } else {
            raw_keypoints.clone()
        };

        // ── One Euro filter ──
        let filtered = if config.filter_config.filter_enabled {
            keypoint_filter.filter(&gated)
        } else {
            gated
        };

        // ── Publish output ──
        let output = AggregatorOutput {
            frame_number,
            camera_outputs,
            keypoints_raw: raw_keypoints,
            keypoints_filtered: filtered,
            frontend_payload_bytes: Vec::new(), // populated from distributor slot
            timestamp_ns: 0.0,
            camera_fps: 0.0,
        };

        *agg.output_slot.lock().unwrap() = Some(output);
    }
}

// ── Filter stubs (to be replaced with real implementations) ──

struct OneEuroFilter {
    min_cutoff: f64,
    beta: f64,
    d_cutoff: f64,
}

impl OneEuroFilter {
    fn new(min_cutoff: f64, beta: f64, d_cutoff: f64) -> Self {
        Self { min_cutoff, beta, d_cutoff }
    }

    fn set_params(&mut self, min_cutoff: f64, beta: f64, d_cutoff: f64) {
        self.min_cutoff = min_cutoff;
        self.beta = beta;
        self.d_cutoff = d_cutoff;
    }

    fn filter(&mut self, points: &HashMap<String, [f64; 3]>) -> HashMap<String, [f64; 3]> {
        // Stub: pass-through. Real implementation in filtering/ module.
        points.clone()
    }
}

struct RealtimePointGate {
    max_velocity: f64,
    max_streak: u32,
}

impl RealtimePointGate {
    fn new(max_velocity: f64, max_streak: u32) -> Self {
        Self { max_velocity, max_streak }
    }

    fn set_max_velocity(&mut self, v: f64) { self.max_velocity = v; }
    fn set_max_streak(&mut self, s: u32) { self.max_streak = s; }

    fn gate(&mut self, points: &HashMap<String, [f64; 3]>) -> HashMap<String, [f64; 3]> {
        // Stub: pass-through. Real implementation in filtering/ module.
        points.clone()
    }
}
```

- [ ] **Step 2: Update src/pipeline/mod.rs**

```rust
pub mod aggregator;
pub mod camera_node;
pub mod config;
pub mod distributor;
pub mod types;
```

---

### Task 10: Create filtering and triangulation module stubs

**Files:**
- Create: `freemocap-rust/src/filtering/mod.rs`
- Create: `freemocap-rust/src/triangulation/mod.rs`
- Modify: `freemocap-rust/src/lib.rs` (already has the mod declarations)

These are placeholder modules for the real filter and triangulation implementations that will be built in the next milestone. The stub structs in `aggregator.rs` will be replaced with imports from these modules.

- [ ] **Step 1: Write src/filtering/mod.rs**

```rust
//! Signal processing filters for real-time keypoint smoothing.
//!
//! Filters operate on `HashMap<String, [f64; 3]>` — point name → 3D coordinates.
//! All filters are stateful (maintain history across frames).

pub mod one_euro;
pub mod velocity_gate;
pub mod skeleton_filter;

// Re-export for convenience
pub use one_euro::OneEuroFilter;
pub use velocity_gate::RealtimePointGate;
```

- [ ] **Step 2: Write module stubs**

`freemocap-rust/src/filtering/one_euro.rs`:
```rust
//! One Euro filter: low-pass filter with adaptive cutoff frequency.
//! Placeholder — implementation deferred to next milestone.

use std::collections::HashMap;

pub struct OneEuroFilter {
    pub min_cutoff: f64,
    pub beta: f64,
    pub d_cutoff: f64,
}

impl OneEuroFilter {
    pub fn new(min_cutoff: f64, beta: f64, d_cutoff: f64) -> Self {
        Self { min_cutoff, beta, d_cutoff }
    }

    pub fn set_params(&mut self, min_cutoff: f64, beta: f64, d_cutoff: f64) {
        self.min_cutoff = min_cutoff;
        self.beta = beta;
        self.d_cutoff = d_cutoff;
    }

    pub fn filter(&mut self, points: &HashMap<String, [f64; 3]>) -> HashMap<String, [f64; 3]> {
        points.clone() // stub: pass-through
    }
}
```

`freemocap-rust/src/filtering/velocity_gate.rs`:
```rust
//! Velocity gate: rejects teleportation spikes.
//! Placeholder — implementation deferred to next milestone.

use std::collections::HashMap;

pub struct RealtimePointGate {
    pub max_velocity_m_per_s: f64,
    pub max_rejected_streak: u32,
}

impl RealtimePointGate {
    pub fn new(max_velocity_m_per_s: f64, max_rejected_streak: u32) -> Self {
        Self { max_velocity_m_per_s, max_rejected_streak }
    }

    pub fn set_max_velocity(&mut self, v: f64) { self.max_velocity_m_per_s = v; }
    pub fn set_max_streak(&mut self, s: u32) { self.max_rejected_streak = s; }

    pub fn gate(&mut self, points: &HashMap<String, [f64; 3]>) -> HashMap<String, [f64; 3]> {
        points.clone() // stub: pass-through
    }
}
```

`freemocap-rust/src/filtering/skeleton_filter.rs`:
```rust
//! FABRIK-based skeleton constraint filter.
//! Placeholder — implementation deferred. Requires skeleton definition
//! and anthropometric prior, same as Python's RealtimeSkeletonFilter.
```

- [ ] **Step 3: Write src/triangulation/mod.rs**

```rust
//! 3D triangulation from multi-camera observations.
//!
//! Takes 2D charuco corner detections from N cameras and computes
//! 3D positions using stereo calibration parameters (DLT method).

pub mod charuco;
```

`freemocap-rust/src/triangulation/charuco.rs`:
```rust
//! Charuco corner triangulation via Direct Linear Transform.
//! Placeholder — implementation deferred to next milestone.
//!
//! Input: Vec of (camera_id, intrinsics, extrinsics, 2D corner points)
//! Output: HashMap<corner_id, [x, y, z]>

use std::collections::HashMap;

/// Triangulate a set of charuco corners observed across multiple cameras.
///
/// Returns a map from corner ID to 3D position. Corners seen in fewer
/// than 2 cameras are skipped.
pub fn triangulate_charuco_corners(
    _observations_by_camera: &HashMap<String, Vec<(i32, [f64; 2])>>,
) -> HashMap<i32, [f64; 3]> {
    HashMap::new() // stub
}
```

---

### Task 11: Create PyO3 Bridge

**Files:**
- Create: `freemocap-rust/src/pyo3_bridge/mod.rs`
- Create: `freemocap-rust/src/pyo3_bridge/py_pipeline.rs`
- Create: `freemocap-rust/src/pyo3_bridge/types.rs`
- Modify: `freemocap-rust/src/lib.rs` (already has the mod declaration)

The PyO3 bridge exposes `Pipeline` as a `#[pyclass]` that Python imports as `_freemocap_rust.Pipeline`. Follows skellytracker's bridge pattern: module init registers classes, pyclass wraps the Rust pipeline with `Mutex` for thread safety.

- [ ] **Step 1: Write src/pyo3_bridge/types.rs**

```rust
//! Python-facing type equivalents.
//! Currently minimal — most types are passed as JSON strings or dicts.
```

- [ ] **Step 2: Write src/pyo3_bridge/py_pipeline.rs**

```rust
use std::sync::{Arc, Mutex, RwLock, atomic::AtomicBool};
use std::sync::mpsc;
use std::thread::JoinHandle;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use crate::pipeline::distributor::{self, Distributor, PipelineCommand};
use crate::pipeline::camera_node::{self, CameraNode};
use crate::pipeline::aggregator::{self, Aggregator};
use crate::pipeline::types::{DistributorSlot, AggregatorOutput, CameraNodeOutput};
use crate::pipeline::config::PipelineConfig;
use skellycam::camera_group::sync_utils::BreakableBarrier;
use skellytracker::trackers::charuco::CharucoTracker;

#[pyclass]
pub struct PyPipeline {
    /// The pipeline state. None after shutdown.
    _config: PipelineConfig,
    group_id: String,
    camera_ids: Vec<String>,
    /// Command senders for each node (kept for shutdown).
    cmd_senders: Vec<mpsc::Sender<PipelineCommand>>,
    /// Aggregator output slot — polled by Python.
    output_slot: Arc<Mutex<Option<AggregatorOutput>>>,
    /// Shutdown flag.
    shutdown_flag: Arc<AtomicBool>,
    /// Thread handles. Joined on shutdown.
    handles: Option<Vec<JoinHandle<()>>>,
}

#[pymethods]
impl PyPipeline {
    #[new]
    fn new(
        _camera_group_manager: Py<PyAny>,
        config_json: &str,
        camera_ids: Vec<String>,
    ) -> PyResult<Self> {
        let config: PipelineConfig = serde_json::from_str(config_json)
            .map_err(|e| {
                pyo3::exceptions::PyValueError::new_err(
                    format!("Invalid pipeline config JSON: {e}")
                )
            })?;

        // For now, generate a placeholder group_id. In the real implementation,
        // this is extracted from the camera_group_manager PyO3 wrapper.
        let group_id = String::from("default");

        let shutdown_flag = Arc::new(AtomicBool::new(false));
        let output_slot = Arc::new(Mutex::new(None::<AggregatorOutput>));

        let n_cameras = camera_ids.len();
        let barrier = Arc::new(BreakableBarrier::new(n_cameras + 1));
        let slot = Arc::new(RwLock::new(DistributorSlot {
            frame_number: -1,
            per_camera_jpegs: Vec::new(),
            frontend_payload_bytes: Vec::new(),
            timestamp_ns: 0.0,
            camera_fps: 0.0,
        }));

        // Command channels for each node
        let mut cmd_senders: Vec<mpsc::Sender<PipelineCommand>> = Vec::new();

        // Distributor command channel
        let (dist_cmd_tx, dist_cmd_rx) = mpsc::channel();
        cmd_senders.push(dist_cmd_tx);

        // Camera node command + output channels
        let mut camera_rxs: Vec<(String, mpsc::Receiver<CameraNodeOutput>)> = Vec::new();
        for cam_id in &camera_ids {
            let (cam_cmd_tx, cam_cmd_rx) = mpsc::channel();
            let (cam_out_tx, cam_out_rx) = mpsc::channel();
            cmd_senders.push(cam_cmd_tx);
            // Camera nodes will be spawned in start() — we store the receivers now.
            // (In the real impl, we store cam_cmd_rx and cam_out_tx in CameraNode)
            camera_rxs.push((cam_id.clone(), cam_out_rx));
        }

        // Aggregator command channel
        let (agg_cmd_tx, agg_cmd_rx) = mpsc::channel();
        cmd_senders.push(agg_cmd_tx);

        Ok(PyPipeline {
            _config: config,
            group_id,
            camera_ids: camera_ids.clone(),
            cmd_senders,
            output_slot,
            shutdown_flag,
            handles: None,
        })
    }

    fn start(&mut self) -> PyResult<()> {
        if self.handles.is_some() {
            return Err(pyo3::exceptions::PyRuntimeError::new_err("Pipeline already started"));
        }

        // Stub: thread spawning deferred to next milestone.
        // The skeleton is in place — real threads will be spawned here
        // following the same pattern as CameraGroup::start() in skellycam.

        Ok(())
    }

    fn shutdown(&mut self) -> PyResult<()> {
        self.shutdown_flag.store(true, std::sync::atomic::Ordering::SeqCst);

        // Send shutdown to all nodes
        for sender in &self.cmd_senders {
            let _ = sender.send(PipelineCommand::Shutdown);
        }

        // Join all thread handles
        if let Some(handles) = self.handles.take() {
            for handle in handles {
                let _ = handle.join();
            }
        }

        Ok(())
    }

    fn update_config(&self, config_json: &str) -> PyResult<()> {
        let config: PipelineConfig = serde_json::from_str(config_json)
            .map_err(|e| {
                pyo3::exceptions::PyValueError::new_err(
                    format!("Invalid pipeline config JSON: {e}")
                )
            })?;

        for sender in &self.cmd_senders {
            sender.send(PipelineCommand::UpdateConfig(config.clone()))
                .map_err(|e| {
                    pyo3::exceptions::PyRuntimeError::new_err(
                        format!("Failed to send config update: {e}")
                    )
                })?;
        }

        Ok(())
    }

    fn get_latest_output(&self, py: Python<'_>) -> PyResult<Option<Py<PyDict>>> {
        let guard = self.output_slot.lock()
            .map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!("Lock poisoned: {e}"))
            })?;

        match guard.as_ref() {
            Some(output) => {
                let dict = PyDict::new(py);
                dict.set_item("frame_number", output.frame_number)?;
                dict.set_item("camera_ids", &self.camera_ids)?;
                Ok(Some(dict.into()))
            }
            None => Ok(None),
        }
    }

    fn camera_ids(&self) -> Vec<String> {
        self.camera_ids.clone()
    }

    fn alive(&self) -> bool {
        !self.shutdown_flag.load(std::sync::atomic::Ordering::Relaxed)
    }
}

impl Drop for PyPipeline {
    fn drop(&mut self) {
        if !self.shutdown_flag.load(std::sync::atomic::Ordering::Relaxed) {
            self.shutdown_flag.store(true, std::sync::atomic::Ordering::SeqCst);
            for sender in &self.cmd_senders {
                let _ = sender.send(PipelineCommand::Shutdown);
            }
            if let Some(handles) = self.handles.take() {
                for handle in handles {
                    let _ = handle.join();
                }
            }
        }
    }
}
```

- [ ] **Step 3: Write src/pyo3_bridge/mod.rs**

```rust
//! PyO3 bridge module — exposes the pipeline engine to Python.
//!
//! Python imports `_freemocap_rust.Pipeline` and controls lifecycle:
//!   pipeline = _freemocap_rust.Pipeline(manager, config_json, camera_ids)
//!   pipeline.start()
//!   output = pipeline.get_latest_output()
//!   pipeline.shutdown()

mod py_pipeline;
mod types;

use pyo3::prelude::*;

#[pymodule]
fn _freemocap_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Initialize logging (idempotent — skellycam may have already called this).
    // Uses skellycam's SkellyFormat for consistent pipe-delimited terminal output.
    skellycam::init_logging(crate::DEFAULT_LOG_LEVEL);

    m.add_class::<py_pipeline::PyPipeline>()?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("__doc__", "FreeMoCap Rust pipeline engine")?;

    Ok(())
}
```

---

### Task 12: Compile Check and Fix

**Files:**
- All files created in Tasks 1-11.

The goal is `cargo check` passing. This validates path dependencies resolve, all types are correct, and the crate compiles against the sibling crate APIs.

- [ ] **Step 1: Run cargo check**

Run: `cargo check --manifest-path freemocap-rust/Cargo.toml 2>&1`

- [ ] **Step 2: Fix any compilation errors**

Common issues and fixes:
- **Missing `frame_number` on `RawFrame`**: Check the actual struct definition. If it doesn't have `frame_number`, derive it from the `FrontendPayload` instead (which does have it).
- **opencv `Vector` import**: `use opencv::core::Vector;`
- **CharucoObservation missing `Box`**: Verify the observation can be boxed. If `CharucoObservation` is not `Send`, wrap in `Arc<Mutex<>>` instead.
- **RawFrame `frame_number`**: Let me check this now...

Actually, let me look at the RawFrame struct more carefully — I saw it has `camera_id`, `camera_index`, `width`, `height`, `jpeg_bytes`. No `frame_number`. The `FrontendPayload` has `frame_number`. So in the distributor, we need to derive frame_number from the `FrontendPayload`:
```rust
let frame_number = frontend_payload.frame_number;
```
This is already what the code in Task 7 does (it reads from `frontend_payload.frame_number`). The `raw_frames[0].frame_number` line in the original stub was wrong — let me fix that.

- [ ] **Step 3: Fix distributor frame_number derivation**

In `distributor.rs`, check/fix the frame_number source:
```rust
// CORRECT: frame_number comes from FrontendPayload, not RawFrame
let frame_number = frontend_payload.frame_number;
```

- [ ] **Step 4: Verify cargo check passes**

Run: `cargo check --manifest-path freemocap-rust/Cargo.toml 2>&1`
Expected: `Finished` with no errors. Warnings for unused imports/variables are acceptable.

---

### Task 13: Write Python Adapter Class

**Files:**
- Create: `freemocap/core/pipeline/realtime/rust_pipeline_adapter.py`

The Python-side adapter following skellycam's pattern. No `USE_RUST_BACKEND` flag here — that lives in the manager.

- [ ] **Step 1: Write rust_pipeline_adapter.py**

```python
"""
RustRealtimePipeline: thin adapter around _freemocap_rust.Pipeline.

The backend decision (Rust vs Python) is made by RealtimePipelineManager,
not here. This class is a simple wrapper with no backend flag.
"""
import logging
import os
import uuid
from typing import Optional

from freemocap.core.pipeline.abcs.pipeline_abc import PipelineABC
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt
from freemocap.core.viz.frontend_payload import FrontendImagePacket, FrontendPayload

logger = logging.getLogger(__name__)

_native = None


def _get_native():
    global _native
    if _native is not None:
        return _native

    # OpenCV DLL discovery (same pattern as skellytracker)
    opencv_bin = "C:/tools/opencv/build/x64/vc16/bin"
    if os.path.isdir(opencv_bin):
        os.add_dll_directory(opencv_bin)

    import _freemocap_rust
    _native = _freemocap_rust
    return _native


class RustRealtimePipeline(PipelineABC):
    """Wraps _freemocap_rust.Pipeline. Thin — no backend flag, no factory."""

    def __init__(
        self,
        *,
        camera_group,
        pipeline_config: RealtimePipelineConfig,
        realtime_camera_ids: list[str] | None = None,
    ):
        self._id: PipelineIdString = str(uuid.uuid4())[:6]
        self._camera_group = camera_group

        cam_ids = realtime_camera_ids or list(camera_group.configs.keys())
        native = _get_native()

        # Get the skellycam PyO3 manager handle
        native_manager = camera_group._native_manager

        self._inner = native.Pipeline(
            native_manager,
            pipeline_config.model_dump_json(),
            cam_ids,
        )

    @property
    def id(self) -> PipelineIdString:
        return self._id

    @property
    def camera_group(self):
        return self._camera_group

    @property
    def camera_ids(self) -> list[str]:
        return self._inner.camera_ids()

    @property
    def camera_group_id(self):
        return self._camera_group.id

    @property
    def alive(self) -> bool:
        return self._inner.alive()

    def start(self) -> None:
        logger.info(f"Starting RustRealtimePipeline [{self._id}]")
        self._inner.start()

    def shutdown(self) -> None:
        logger.info(f"Shutting down RustRealtimePipeline [{self._id}]")
        self._inner.shutdown()

    def update_config(self, new_config: RealtimePipelineConfig) -> None:
        self._inner.update_config(new_config.model_dump_json())

    def get_latest_frontend_payload(
        self, if_newer_than: FrameNumberInt
    ) -> FrontendImagePacket | None:
        output = self._inner.get_latest_output()
        if output is None:
            return None

        frame_number = output["frame_number"]
        if frame_number <= if_newer_than:
            return None

        # Construct frontend packet from aggregator output
        # (Full binary payload construction deferred — currently returns
        #  the skellycam payload bytes that rode through the pipeline.)
        return FrontendImagePacket(
            images_bytearray=bytearray(),  # populated from payload in next milestone
            multiframe_timestamp=0.0,
            frontend_payload=FrontendPayload(
                frame_number=frame_number,
                camera_group_id=self.camera_group_id,
            ),
        )
```

- [ ] **Step 2: Verify the file imports correctly**

Since `_freemocap_rust` isn't built yet, this will fail at import. Create a try/except guard:

```python
try:
    import _freemocap_rust
    _FREEMOCAP_RUST_AVAILABLE = True
except ImportError:
    _FREEMOCAP_RUST_AVAILABLE = False
    logger.debug("_freemocap_rust not available — Rust pipeline disabled")
```

---

### Task 14: Commit

- [ ] **Step 1: Review all created files**

Run: `git -C freemocap-rust status` (if freemocap-rust is its own git repo)
Or: `git status` from the freemocap root to see new files.

- [ ] **Step 2: Stage and commit**

```bash
git add freemocap-rust/Cargo.toml
git add freemocap-rust/pyproject.toml
git add freemocap-rust/.cargo/config.toml
git add freemocap-rust/src/
git add freemocap/core/pipeline/realtime/rust_pipeline_adapter.py
git commit -m "feat: scaffold freemocap-rust crate with pipeline module structure

Initialize freemocap-rust as a PyO3 module with path dependencies on
skellycam-rust and skellytracker-rust. Stub out all pipeline modules:
distributor (BreakableBarrier fan-out), camera_node (charuco detection),
aggregator (fan-in + filtering), filtering (One Euro + velocity gate),
triangulation (charuco DLT), and PyO3 bridge.

Architecture follows the freemocap-architecture design docs.
Cargo.toml matches skellytracker edition 2021 conventions.
```
```

---

## Verification Checklist

After all tasks complete, verify:

- [ ] `cargo check --manifest-path freemocap-rust/Cargo.toml` passes with zero errors
- [ ] `cargo check --manifest-path freemocap-rust/Cargo.toml --no-default-features` passes (rlib mode for rust-analyzer)
- [ ] All modules declared in `lib.rs` have corresponding files
- [ ] Path dependencies resolve: `skellycam` and `skellytracker` crates found
- [ ] `PipelineCommand` variants are `Clone` (required for sending to multiple nodes)
- [ ] All public types in `types.rs` are `Send + Sync` (thread boundary crossing)
- [ ] `PyPipeline` Drop impl calls shutdown (safety net)
- [ ] Python adapter handles `ImportError` for `_freemocap_rust`
```
