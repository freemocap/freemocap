# FreeMoCap Rust — Posthoc Pipeline Handoff

## Session Summary (2026-05-26)

The freemocap-rust real-time pipeline engine is now **fully wired end-to-end** for charuco detection → triangulation. The aggregator loads calibration, calls `triangulate_charuco_corners()` with DLT + weighted subset-ensemble outlier rejection, and feeds real 3D points through velocity gate → One Euro filter. An E2E test spawns the full thread topology (distributor→barrier→camera nodes→aggregator) fed by VideoGroup, producing 400 triangulated points at 1892mm scale from the test data (30 frames, 3 cameras).

## What Changed This Session

### Triangulation wired into aggregator
- `src/pipeline/aggregator.rs`: Added `calibration`, `triangulation_enabled`, `rejection_config`, `max_reprojection_error_px` fields. Replaced `HashMap::new()` stub with real `triangulate_charuco_corners()` call. Aggregator extracts `detected_charuco_corner_ids` + `detected_charuco_corners_image_coordinates` from `CharucoObservation`, groups by corner ID across cameras, calls triangulation, feeds results into filter chain.
- `src/pyo3_bridge/py_pipeline.rs`: Added missing fields to `Aggregator` construction (calibration: None, defaults for rejection config).

### Comprehensive tracing logs
All pipeline threads now emit structured `tracing` logs at every level:
- **TRACE**: barrier wait/release, individual recv() calls, per-corner triangulation results
- **DEBUG**: per-cycle summaries (frame N, N cameras, N points, timing)
- **INFO**: thread lifecycle (started, shutting down)
- **WARN**: recoverable problems (JPEG decode failure, frame mismatch, missing calibration)
- **ERROR**: terminal conditions (removed - all errors are now warnings or handled via channel disconnect)

Log format uses `SkellyFormat` (pipe-delimited, matching skellycam's convention).

### E2E pipeline test
- `src/video_reader/pipeline_test.rs`: Complete rewrite. Spawns full thread topology (1 distributor + 3 camera nodes + 1 aggregator with BreakableBarrier), feeds VideoGroup frames through mock FrameSlots, verifies triangulated output. 30 frames, ~3s runtime, 9.7 fps throughput (test harness limited — includes JPEG encode overhead).

### Shutdown fixes
- `barrier.break_barrier()` called **before** dropping command senders — prevents rendezvous channel deadlock.
- All `Sender` handles dropped before `join()` calls — ensures channel disconnection unblocks `recv()`.
- Aggregator uses clean `recv()` (no timeout/polling). Shutdown flow: barrier break → camera nodes exit → output Senders drop → aggregator recv() returns `Err(RecvError)` → breaks.

### Cleanup
- Moved `use` statements from bottom to top of `src/pipeline_manager/mod.rs`
- Removed duplicate `#[cfg(test)]` in `src/video_reader/mod.rs`
- Replaced all `eprintln!`/`println!` with proper `tracing` macros
- Fixed `CharucoObservation` field names: `detected_charuco_corner_ids`, `detected_charuco_corners_image_coordinates`

## Current State

### What Works (real, tested)
| Component | Status | File |
|-----------|--------|------|
| DLT triangulation (SVD) | ✅ | `src/triangulation/dlt.rs` |
| Outlier rejection (weighted ensemble) | ✅ | `src/triangulation/outlier_rejection.rs` |
| Charuco corner grouping + undistortion | ✅ | `src/triangulation/charuco.rs` |
| Calibration TOML loader | ✅ | `src/triangulation/calibration_loader.rs` |
| One Euro filter | ✅ | `src/filtering/one_euro.rs` |
| Velocity gate | ✅ | `src/filtering/velocity_gate.rs` |
| Distributor (FrameSlots polling + Barrier fan-out) | ✅ | `src/pipeline/distributor.rs` |
| Camera node (JPEG decode + charuco detect) | ✅ | `src/pipeline/camera_node.rs` |
| Aggregator (collect + triangulate + filter + publish) | ✅ | `src/pipeline/aggregator.rs` |
| VideoGroup (synchronized multi-video reader) | ✅ | `src/video_reader/mod.rs` |
| E2E pipeline test | ✅ | `src/video_reader/pipeline_test.rs` |
| All 10 tests pass | ✅ | `cargo test --lib` |

### What's Stubbed/Deferred
| Component | Status |
|-----------|--------|
| PipelineManager thread spawning (HTTP path) | ❌ Stores config, doesn't spawn |
| PipelineManager config update | ❌ `let _ = &config;` no-op |
| Posthoc pipeline | ❌ `unimplemented!()` |
| Skeleton filter (FABRIK) | ❌ Placeholder comment |
| `maturin develop` / PyO3 .pyd | ❌ Not built |
| Real-time server smoke test | ❌ Not tested with live cameras |

## Next: Posthoc Pipeline

### What It Should Be
A posthoc processing pipeline that:
1. Reads synchronized multi-camera video files (via VideoGroup or similar)
2. Runs per-frame charuco detection on each camera stream
3. Triangulates 3D points across cameras
4. Exports results (3D trajectories, per-camera weights, reprojection error)

### Relationship to Existing Code

The E2E test in `src/video_reader/pipeline_test.rs` is essentially a **prototype posthoc pipeline** — it reads videos, spawns the full thread topology, and collects triangulated output. The next step is to extract this into a properly architected `PosthocPipeline` struct/subsystem rather than having it live in a test function.

### VideoGroup → Production Upgrade Path

The current `VideoGroup` (`src/video_reader/mod.rs`) is functional but minimal:
- Opens N video files via OpenCV `VideoCapture`
- Reads frames sequentially in lockstep
- Verifies matching frame counts at open time

For a production posthoc pipeline, VideoGroup should be upgraded to:
- **Configurable backends**: `CAP_ANY` → `CAP_FFMPEG` for better codec support, or `ffmpeg-sidecar` for frame-accurate seeking
- **Frame-accurate sync**: The current sequential-read guarantee works for posthoc, but if seeking is needed, sync-by-frame-number (matching skellycam's `RawFrame.frame_number`) is required
- **Timing infrastructure**: Unlike real-time (where skellycam provides timestamps), posthoc needs to synthesize timestamps — frame index × (1/fps) from video metadata
- **Streaming API**: An iterator-like interface that yields synchronized `(frame_number, Vec<Mat>)` tuples, matching the real-time pipeline's `FrameSlots` consumption pattern

### What to Reference

**Python code** (the existing posthoc pipeline):
- `freemocap/core/pipeline/posthoc/posthoc_aggregation_node.py` — collects all video node outputs into `video_outputs_by_frame` dict, calls task function
- `freemocap/core/tasks/mocap/posthoc_mocap_task.py` — builds per-camera `BaseRecorder` objects from observations, loads calibration, calls skeleton reconstruction
- `freemocap/core/tasks/mocap/mocap_helpers/skeleton_from_mediapipe_observations.py` — extracts `(n_frames, n_points, 2)` arrays from recorders, calls `triangulator.triangulate()`

**Key difference from Python**: The Python posthoc pipeline collects ALL observations first (into recorders/dicts), then triangulates in one batch. The Rust posthoc pipeline can do the same (batch triangulation via `triangulate_simple_batch()`), OR it can process frame-by-frame through the real-time thread topology (which is what the E2E test already does).

**Rust code to build on**:
- `src/triangulation/charuco.rs::triangulate_charuco_corners()` — the core triangulation function
- `src/triangulation/dlt.rs::triangulate_simple_batch()` — vectorized batch DLT for posthoc
- `src/video_reader/mod.rs::VideoGroup` — multi-video reader (needs upgrading)
- `src/video_reader/pipeline_test.rs` — prototype posthoc pipeline (extract from test → production code)

### Architecture Sketch

```
PosthocPipeline {
    video_group: VideoGroup,           // upgraded multi-video reader
    calibration: HashMap<String, CameraModel>,
    detectors: Vec<CharucoTracker>,    // one per camera
    config: PipelineConfig,
}

impl PosthocPipeline {
    /// Run detection + triangulation on all frames, returning results.
    fn run(&mut self) -> PosthocResult {
        for each synchronized multi-frame from VideoGroup:
            for each camera:
                charuco_detection(frame) -> observations
            triangulate_charuco_corners(observations, calibration) -> 3d_points
            accumulate into PosthocResult
    }
}

PosthocResult {
    frames: Vec<FrameResult>,          // per-frame 3D points
    camera_weights: ...                // per-camera confidence
    reprojection_errors: ...           // quality metrics
    stats: ProcessingStats,            // timing, throughput
}
```

The key question for the next agent: **batch processing or frame-by-frame?**
- **Batch**: Collect all observations, triangulate once (faster, matches Python). Use `triangulate_simple_batch()`.
- **Frame-by-frame**: Process through thread topology (matches real-time, reusable code). Use `run_distributor`/`run_camera_node`/`run_aggregator`.

Recommendation: start with batch (simpler, matches Python for easy validation), then thread topology version (reuses real-time code, same architecture as the E2E test).

### Testing

Test data is at `C:\Users\jonma\freemocap_data\recordings\freemocap_test_data`:
- 3 synchronized videos (222 frames, 720×1280, 6fps, mpeg4)
- Calibration TOML: `freemocap_test_data_camera_calibration.toml`
- Pre-computed charuco observations: `output_data/charuco_observations.json` (for validation)
- Expected: ~1023 triangulated 3D points, ~2100mm mean distance from origin

## Key Files

| File | Purpose |
|------|---------|
| `freemocap-rust/src/pipeline/aggregator.rs` | Aggregator with triangulation wired in |
| `freemocap-rust/src/pipeline/distributor.rs` | Frame fan-out with BreakableBarrier |
| `freemocap-rust/src/pipeline/camera_node.rs` | JPEG decode + charuco detection |
| `freemocap-rust/src/triangulation/charuco.rs` | Corner grouping + triangulation + reprojection gate |
| `freemocap-rust/src/triangulation/outlier_rejection.rs` | Weighted subset-ensemble algorithm |
| `freemocap-rust/src/triangulation/dlt.rs` | DLT via SVD + batch triangulation |
| `freemocap-rust/src/filtering/one_euro.rs` | Adaptive low-pass filter |
| `freemocap-rust/src/filtering/velocity_gate.rs` | Teleportation spike rejection |
| `freemocap-rust/src/video_reader/mod.rs` | Multi-video synchronized reader |
| `freemocap-rust/src/video_reader/pipeline_test.rs` | E2E pipeline test (prototype posthoc) |
| `rearchitecture-docs/freemocap-architecture/README.md` | Architecture status table |
| `rearchitecture-docs/freemocap-architecture/05-aggregator.md` | Aggregator design doc |

## Quick Reference

```bash
cd C:\Users\jonma\code_repos\github\freemocap\freemocap\freemocap-rust

cargo check              # type checking (~2s)
cargo build --lib        # builds cdylib + rlib
cargo test --lib          # 10 tests, all pass
cargo test --lib video_reader::pipeline_test -- --nocapture  # E2E test with logs
```

Log levels: `freemocap=trace` for hot-loop debugging, `freemocap=debug` for per-cycle diagnostics, `freemocap=info` for normal operation. Default is `freemocap=debug,skellycam=info,info`.
