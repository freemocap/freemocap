# FreeMoCap Rust — Handoff (2026-05-27)

## Session Summary

Two major architectural changes landed:

1. **Composable per-loop timestamp architecture** — `PipelineTimestamps` was a flat
   struct mixing distributor and aggregator stages. It's now split into four
   composable structs: `DistributorTimestamps`, `CameraNodeTimestamps`,
   `AggregatorTimestamps`, and the composite `PipelineCycleTimestamps`. Every
   thread loop gets its own `Timestamps` struct with named stage boundaries and
   `end − start` duration helpers. The same pattern was applied upstream in
   skellycam: `MultiFramePayload` now wraps `GathererTimestamps` instead of
   carrying bare `i64` fields.

2. **VideoGroup uses mpsc channel instead of FrameSlots** — The video path no
   longer polls `FrameSlots` (which was designed for live cameras where you
   always want the latest frame). Instead, the video dispatcher sends
   `MultiFramePayload` (skellycam's type) on an unbounded `mpsc` channel. The
   distributor receives via `recv()` — no pacing signal, no spin-waits, no
   frame dropping. The distributor checks `video_rx.is_some()` to decide
   between channel (video) and FrameSlots (live camera) input.

## What Changed This Session

### Composable per-loop timestamps

**freemocap** (`src/pipeline/types.rs`):
- `PipelineTimestamps` (flat, 7 mixed fields) → 4 composable structs:
  - `DistributorTimestamps`: `cycle_start`, `slot_write_done`, `barrier_release`, `barrier_return`
  - `CameraNodeTimestamps` (was `DetectionTimestamps`): `source: SourceFrameTimestamps`, `dequeue`, `post_jpeg_decode`, `post_detection`, `pre_send`
  - `AggregatorTimestamps`: `collection_start`, `all_received`, `post_triangulation`, `post_filtering`, `output_published`
  - `PipelineCycleTimestamps`: composite of `distributor: DistributorTimestamps` + `cameras: HashMap<String, CameraNodeTimestamps>` + `aggregator: AggregatorTimestamps`
- Each struct has duration helpers (`slot_work_ns()`, `triangulation_ns()`, etc.)
- `AggregatorOutput.pipeline_timestamps` → `cycle_timestamps: PipelineCycleTimestamps`

**skellycam** (`camera/types.rs`, `camera_group/`):
- `GathererTimestamps` moved from `camera_group` to `camera::types`
- `MultiFramePayload` now has `gatherer_timestamps: GathererTimestamps` instead of three bare `i64` fields (`all_frames_received_ns`, `payload_assembled_ns`, `pre_send_downstream_ns`)
- Updated `gatherer.rs`, `recording_stats.rs`, `camera_group.rs`, `camera_group/mod.rs`

### VideoGroup: FrameSlots → mpsc channel

**`src/video_reader/`**:
- `reader.rs` (new): `VideoReader` wraps OpenCV `VideoCapture` with metadata (FPS, dims, frame count)
- `dispatcher.rs` (rewritten): Reads frames sequentially, JPEG-encodes, builds `FramePacket`s, assembles `MultiFramePayload`, sends on `mpsc::Sender<MultiFramePayload>`. No FrameSlots, no pacing signal.
- `mod.rs` (rewritten): `VideoGroup` with `Created→Streaming→Stopped` lifecycle. `open()` → `start()` creates channel + spawns dispatcher → `take_video_receiver()` returns `mpsc::Receiver<MultiFramePayload>` → `shutdown()`.

**`src/pipeline/distributor.rs`**:
- `Distributor` has new `video_rx: Option<Receiver<MultiFramePayload>>` field
- When `video_rx.is_some()`: blocks on `recv()`, converts `FramePacket` → `RawFrame` data
- When `video_rx.is_none()`: polls `FrameSlots` as before (live camera path)
- Removed pacing signal dependency for video path

### Pipeline timing statistics

**`src/pipeline/stats.rs`** (new): Per-stage, per-camera, per-thread timing statistics with skellycam-format output:
- `VideoDispatcherStats`: read, encode, payload build, slots write
- `DistributorStats`: slot poll+write, barrier wait
- `CameraNodeStats`: JPEG decode, charuco detect, total (per camera)
- `AggregatorStats`: collection, triangulation, filtering, output publish
- `print_pipeline_stats()`: prints tables with median/mean/std/CV%/min/max/n, per-camera breakdowns, mean/median camera summaries, across-camera spread — matching skellycam's gatherer output format

All thread functions (`run_distributor`, `run_camera_node`, `run_aggregator`, `spawn_video_dispatcher`) now return their stats structs. The E2E test collects them and prints the full block.

### E2E test results

```
cargo test --release --lib video_reader::pipeline_test -- --nocapture

Pipeline FPS:    23.5 fps (release build, 30 frames, 3 cameras, 720×1280)
Frame duration:  43.0 ms median

Time breakdown (median):
  Video read (3 cams):     33.1 ms   ← OpenCV CAP_ANY/MSMF backend bottleneck
  JPEG encode (3 cams):    12.4 ms   ← quality 100 at 720×1280
  Distributor:             <1 ms
  JPEG decode (median cam): 4.6 ms   ← per camera, parallel
  Charuco detect (median): 23.9 ms   ← 3× expected (~8ms in skellytracker demo)
  Triangulation + filter:  <1 ms
```

The 33ms video read is the dominant dispatcher cost — likely the MSMF backend
selected by `CAP_ANY` on Windows. Switching to `CAP_FFMPEG` should improve this.

## Current State

### What Works (real, tested — 11 tests pass)

| Component | File |
|-----------|------|
| DLT triangulation (SVD) | `src/triangulation/dlt.rs` |
| Outlier rejection (weighted ensemble) | `src/triangulation/outlier_rejection.rs` |
| Charuco corner grouping + undistortion | `src/triangulation/charuco.rs` |
| Calibration TOML loader | `src/triangulation/calibration_loader.rs` |
| One Euro filter | `src/filtering/one_euro.rs` |
| Velocity gate | `src/filtering/velocity_gate.rs` |
| Distributor (dual-source: FrameSlots or mpsc channel) | `src/pipeline/distributor.rs` |
| Camera node (JPEG decode + charuco detect) | `src/pipeline/camera_node.rs` |
| Aggregator (collect + triangulate + filter + publish) | `src/pipeline/aggregator.rs` |
| VideoGroup (reader + dispatcher + mpsc channel) | `src/video_reader/` |
| VideoReader (single-file reader with metadata) | `src/video_reader/reader.rs` |
| Composable per-loop timestamps | `src/pipeline/types.rs` |
| Pipeline timing statistics | `src/pipeline/stats.rs` |
| E2E pipeline test (VideoGroup → channel → full pipeline) | `src/video_reader/pipeline_test.rs` |
| Upstream: `MultiFramePayload` wraps `GathererTimestamps` | skellycam `camera/types.rs` |

### What's Stubbed/Deferred

| Component | Status |
|-----------|--------|
| PipelineManager thread spawning (HTTP path) | ❌ Stores config, doesn't spawn |
| PipelineManager config update | ❌ `let _ = &config;` no-op |
| Posthoc pipeline (standalone processing mode) | ❌ Infrastructure ready; no `PosthocPipeline` struct yet |
| Skeleton filter (FABRIK) | ❌ Placeholder comment |
| `maturin develop` / PyO3 .pyd | ❌ Not built |
| Real-time server smoke test | ❌ Not tested with live cameras |

## Next Steps

### Immediate

1. **Fix video read performance**: Switch `VideoReader::open()` from `CAP_ANY` →
   `CAP_FFMPEG`. The current 33ms read for 3 frames (10ms each) is the dominant
   dispatcher bottleneck. FFmpeg's software decoder should be 3-5× faster.

2. **Investigate charuco detection speed**: 24ms per camera vs 8ms expected in
   skellytracker webcam demo. Check whether resolution (720×1280 vs the demo's
   likely 640×480) accounts for the 3× gap, or whether there's FFI overhead.

3. **Posthoc pipeline struct**: Build a `PosthocPipeline` that wires VideoGroup →
   channel → distributor → camera nodes → aggregator into a single `run()` call
   that returns `PosthocResult` (all frames, all 3D points, stats). The E2E test
   already does this manually — extract to production code.

### Medium-term

4. **Result export**: Serialize triangulated 3D trajectories + per-camera weights
   + reprojection errors to JSON/CSV matching Python output format.

5. **Batch triangulation mode**: For posthoc, collect all observations first,
   triangulate once via `triangulate_simple_batch()` (avoids per-frame thread
   overhead for pure posthoc use).

6. **`maturin develop`**: Build the `.pyd`, verify `import _freemocap_rust` works.

### Later

7. Skeleton inference (RTMPose per camera or GPU-batched)
8. Real-time server smoke test with live cameras
9. FABRIK skeleton constraint filter

## Key Files

| File | Purpose |
|------|---------|
| `freemocap-rust/src/pipeline/types.rs` | Composable timestamp structs + channel message types |
| `freemocap-rust/src/pipeline/stats.rs` | Per-stage timing statistics + print formatting |
| `freemocap-rust/src/pipeline/distributor.rs` | Dual-source distributor (FrameSlots + mpsc channel) |
| `freemocap-rust/src/pipeline/camera_node.rs` | JPEG decode + charuco detection |
| `freemocap-rust/src/pipeline/aggregator.rs` | Collection + triangulation + filtering + publish |
| `freemocap-rust/src/video_reader/mod.rs` | VideoGroup lifecycle (open/start/shutdown) |
| `freemocap-rust/src/video_reader/reader.rs` | Single video file reader |
| `freemocap-rust/src/video_reader/dispatcher.rs` | BGR→JPEG encode → MultiFramePayload → mpsc channel |
| `freemocap-rust/src/video_reader/pipeline_test.rs` | E2E test: VideoGroup → channel → pipeline → stats |
| `freemocap-rust/src/triangulation/charuco.rs` | Corner grouping + triangulation + reprojection gate |
| `freemocap-rust/src/triangulation/outlier_rejection.rs` | Weighted subset-ensemble algorithm |
| `freemocap-rust/src/triangulation/dlt.rs` | DLT via SVD |
| `skellycam-rust/src/camera/types.rs` | `MultiFramePayload` + `GathererTimestamps` |
| `rearchitecture-docs/freemocap-architecture/README.md` | Architecture status table |
| `rearchitecture-docs/freemocap-architecture/handoff-posthoc-pipeline.md` | This document |

## Quick Reference

```bash
cd C:\Users\jonma\code_repos\github\freemocap\freemocap\freemocap-rust

# Type checking
cargo check --lib

# All 11 tests
cargo test --lib

# E2E test with stats (debug build — slow, for correctness)
cargo test --lib video_reader::pipeline_test -- --nocapture

# E2E test with stats (release build — for timing measurements)
cargo test --release --lib video_reader::pipeline_test -- --nocapture

# Also check skellycam (needed after upstream changes)
cd ../skellycam/skellycam-rust && cargo check --lib
```

Test data: `C:\Users\jonma\freemocap_data\recordings\freemocap_test_data`
- 3 synchronized videos (222 frames, 720×1280, 6fps, mpeg4)
- Calibration TOML: `freemocap_test_data_camera_calibration.toml`
- Pre-computed charuco observations: `output_data/charuco_observations.json`
