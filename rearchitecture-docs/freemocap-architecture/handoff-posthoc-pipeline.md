# FreeMoCap Rust — Handoff (2026-05-27, session 2)

You're picking up work on the FreeMoCap Rust pipeline. The code is at
`C:\Users\jonma\code_repos\github\freemocap\freemocap\freemocap-rust`.

## CRITICAL: DO NOT MAKE ASSUMPTIONS. DO NOT GUESS. DO NOT SKIM.

You must actually read the code files, read the rearchitecture docs, and trace
the data flow before you write a single line. This handoff doc is a MAP, not a
replacement for reading. Use it to know where to look, then go look.

**Before you do anything else, read ALL of these thoroughly:**

1. **This handoff doc** — context, current state, what changed, what's broken
2. **The architecture README:**
   `rearchitecture-docs/freemocap-architecture/README.md` — status table,
   design decisions, upstream changes
3. **The actual Rust source code — every file in these directories:**
   - `src/pipeline/` — distributor, camera_node, aggregator, types, config, stats
   - `src/pyo3_bridge/` — mod.rs, py_pipeline.rs
   - `src/video_reader/` — mod.rs, reader.rs, dispatcher.rs, pipeline_test.rs
   - `src/pipeline_manager/mod.rs`
4. **The Python adapter:**
   - `freemocap/core/pipeline/realtime/rust_pipeline_adapter.py`
   - `freemocap/core/pipeline/realtime/realtime_pipeline_manager.py`
5. **The skellycam PyO3 bridge** (pattern to follow):
   - `skellycam-rust/src/pyo3_bridge/py_camera_group_manager.rs`
   - `skellycam-rust/src/camera/types.rs` — `MultiFramePayload`, `GathererTimestamps`

You need to actually understand:
- How the pipeline threads are spawned and how they return stats
- How `PyPipeline` currently works (and how it's out of sync)
- How the Python `RealtimePipelineManager` creates and manages pipelines
- How `FrameSlots` are extracted from `PyO3CameraGroupManager`
- How the dual-source distributor decides between camera and video input
- How `maturin develop` builds the `.pyd`

**Guardrails:**
- Do NOT touch the server code, HTTP API, or skeleton_filter unless unavoidable.
- Focus on the PyO3 bridge (`py_pipeline.rs`) and the Python integration layer.
- When changing thread function signatures, wrap the call with a closure that
  discards the return value (`{ fn(args); }`) to keep `JoinHandle<()>` working.
- Prefer editing existing files over creating new ones.
- Run `cargo check --tests` after every change. Run `cargo test --lib` before
  claiming completion.
- If you change anything in skellycam or skellytracker (sibling crates), check
  both: `cd ../skellycam/skellycam-rust && cargo check --lib` and
  `cd ../../skellytracker/skellytracker-rust && cargo check --lib`.

## Session Summary

Performance optimization session. Fixed the three largest bottlenecks in the
posthoc pipeline path, taking the E2E test from 23.5 fps to 36.9 fps (57%
improvement). Cleaned up dead code in skellytracker. Updated build docs for
FFmpeg-enabled OpenCV.

### What changed

1. **Video read: CAP_ANY → CAP_FFMPEG** — OpenCV's MSMF backend was taking
   ~10ms per 720×1280 frame. Switched to FFmpeg backend (now 0.9-1.2ms per
   frame). Required rebuilding OpenCV via vcpkg with the `[ffmpeg]` feature.
   Setup instructions updated in both repos.

2. **JPEG quality: 100 → 95** — The dispatcher was encoding BGR frames at
   quality 100 (essentially lossless). Dropping to 95 cuts encode time nearly
   in half (12ms → 8ms for 3 frames) and decode time by ~35% (5ms → 3ms) with
   zero impact on charuco detection accuracy.

3. **Single-call detect_board** — skellytracker's `CharucoTracker::detect()`
   was running marker detection twice: once explicitly in
   `detect_aruco_markers_raw()` (which created a new `ArucoDetector` per
   frame), then again inside `detect_board()` when the pre-detected markers
   didn't match the board. Now `detect_board()` is called with empty containers
   and handles everything in one C++ call — matching Python's `detectBoard()`
   exactly. Removed the dead `detect_aruco_markers_raw` method and the cached
   aruco fields from `CharucoTracker`.

4. **Fixed frame number** — `camera_node.rs` was passing `0` to
   `detector.detect(0, &image)` instead of the actual frame number from the
   distributor slot. Fixed.

5. **Investigated charuco thread contention** — Confirmed that 3 parallel
   `detect_board` calls share OpenCV's global thread pool, causing alternating
   fast (13ms) / slow (25ms) frames. Tried `set_num_threads(1)` (uniform but
   slower at 14-18ms per call) and `set_num_threads(n_cpus/3)` (no measurable
   improvement over default). Reverted both — the single-call detect_board
   change was the real win. The remaining ~20ms/camera charuco time is within
   expected range for 1280×720 at 3-way parallel.

6. **Fixed pre-existing typo** — `c//!` → `//!` in skellytracker's
   `composite_gpu/observation.rs`.

### Performance

```
cargo test --release --lib video_reader::pipeline_test -- --nocapture

Pipeline FPS (median):  36.9 fps  (was 23.5, +57%)
Frame duration (median): 27.5 ms  (was 43.0, -36%)

Video dispatcher (median):
  Read 3 frames:          3.5 ms  (was 33.1,  9.4× faster)
  JPEG encode 3 frames:   7.8 ms  (was 12.4,  1.6× faster)

Camera nodes (median per camera, 3 parallel):
  JPEG decode:            3.0 ms  (was  4.6,  1.5× faster)
  Charuco detect:        20.8 ms  (was 23.9,  1.1× faster)
  Camera total:          24.1 ms

Aggregator (median):
  Triangulation:          0.12 ms
  Filtering:              0.01 ms
  Output publish:        <0.01 ms

Total triangulated 3D points: 397 (30 frames, 3 cameras)
```

## Current State

### What Works (11 tests pass, 36.9 fps release)

| Component | File | Notes |
|-----------|------|-------|
| DLT triangulation (SVD) | `src/triangulation/dlt.rs` | |
| Outlier rejection (weighted ensemble) | `src/triangulation/outlier_rejection.rs` | |
| Charuco corner grouping + undistortion | `src/triangulation/charuco.rs` | |
| Calibration TOML loader | `src/triangulation/calibration_loader.rs` | |
| One Euro filter | `src/filtering/one_euro.rs` | |
| Velocity gate | `src/filtering/velocity_gate.rs` | |
| Distributor (FrameSlots + mpsc channel) | `src/pipeline/distributor.rs` | Dual-source |
| Camera node (JPEG decode + charuco) | `src/pipeline/camera_node.rs` | Single-call detect_board |
| Aggregator (collect + triangulate + filter) | `src/pipeline/aggregator.rs` | |
| VideoGroup (reader + dispatcher + channel) | `src/video_reader/` | mpsc-based |
| VideoReader (FFmpeg backend) | `src/video_reader/reader.rs` | CAP_FFMPEG |
| Composable per-loop timestamps | `src/pipeline/types.rs` | 4 structs |
| Pipeline timing statistics | `src/pipeline/stats.rs` | Skellycam-format tables |
| E2E pipeline test | `src/video_reader/pipeline_test.rs` | 397 pts @ 36.9 fps |
| Single-call charuco detect | skellytracker `charuco/mod.rs` | Matches Python detectBoard |

### What's Broken/Needs Fixing

| Component | Status | Notes |
|-----------|--------|-------|
| PyO3 bridge (`py_pipeline.rs`) | ❌ Out of sync | Thread spawns discard stats return values; `JoinHandle<()>` needs to become `JoinHandle<Stats>` or stats collected via `Arc<Mutex<>>` |
| PyPipeline calibration | ❌ hardcoded `calibration: None` | Aggregator runs but doesn't triangulate |
| PyPipeline video path | ❌ Not implemented | `video_rx: None` — no way to use VideoGroup from Python |
| PipelineManager thread spawning | ❌ Stores config, doesn't spawn | HTTP path untested |
| `maturin develop` / PyO3 .pyd | ❌ Not built | Module exists but untested with latest changes |

## Next Session: PyO3 Bridge Integration

The next session should wire the Rust pipeline into the Python FreeMoCap server
so it can run as a drop-in replacement for the Python backend.

### Architecture constraint

The Rust camera group manager and Rust pipeline manager are a **coupled pair**.
You can't use one without the other — the pipeline pulls `FrameSlots` directly
from the camera group via `Arc` clones. There will be a single `USE_RUST_BACKEND`
flag (module-level constant) that swaps both:

```python
# freemocap/core/pipeline/realtime/realtime_pipeline_manager.py
USE_RUST_BACKEND: bool = False  # True = Rust camera group + Rust pipeline
```

When True, the manager imports `_skellycam_rust` and `_freemocap_rust` and
creates native objects instead of Python multiprocessing wrappers.

### What needs to happen

1. **Fix PyPipeline thread signatures** (`src/pyo3_bridge/py_pipeline.rs`)
   - All thread functions now return stats structs
   - `JoinHandle<()>` needs to become `JoinHandle<StatType>` or the stats need
     to be collected via `Arc<Mutex<Option<StatType>>>`  
   - Or: wrap thread functions in a closure that drops stats: `{ fn(args); }`
     (the handoff doc from last session mentions this pattern)

2. **Wire calibration into PyPipeline**
   - PyPipeline needs to accept a calibration TOML path or pre-parsed models
   - Pass `calibration: Some(camera_models)` to Aggregator
   - Set `triangulation_enabled: true`
   - Expose triangulated keypoints in `get_latest_output()`

3. **Support video (posthoc) path from Python**
   - Add a `PyPosthocPipeline` class or a `source: "camera" | "video"` parameter
   - When source is "video": create VideoGroup, pass `video_rx` to Distributor
   - Need to accept video paths + calibration from Python

4. **Integrate with Python RealtimePipelineManager**
   - Add the `USE_RUST_BACKEND` flag
   - On True: create `PyO3CameraGroupManager` → extract FrameSlots → create PyPipeline
   - Handle lifecycle: create → start → poll output → shutdown
   - Match the existing Python manager's API so callers don't need to change

5. **Build and test the .pyd**
   - `maturin develop` in the freemocap-rust directory
   - Verify `import _freemocap_rust` works
   - Run a smoke test with real cameras or test videos
   - Check that the Python adapter (`rust_pipeline_adapter.py`) still works

6. **Decide on result format**
   - Currently `get_latest_output()` returns a PyDict with frame_number,
     camera_ids, frontend_payload, timestamp_ns, camera_fps
   - Need to add: triangulated keypoints (keypoints_raw, keypoints_filtered),
     per-camera charuco observations, pipeline timing stats
   - Match the Python `AggregatorOutput` format so frontend consumers don't break

### Key files for the PyO3 work

| File | Purpose |
|------|---------|
| `freemocap-rust/src/pyo3_bridge/mod.rs` | `#[pymodule] _freemocap_rust` |
| `freemocap-rust/src/pyo3_bridge/py_pipeline.rs` | PyPipeline pyclass |
| `freemocap/core/pipeline/realtime/rust_pipeline_adapter.py` | Python adapter |
| `freemocap/core/pipeline/realtime/realtime_pipeline_manager.py` | Manager with USE_RUST_BACKEND |
| `skellycam-rust/src/pyo3_bridge/py_camera_group_manager.rs` | PyO3CameraGroupManager |
| `freemocap-rust/src/pipeline/distributor.rs` | Dual-source input (camera/video) |
| `freemocap-rust/src/pipeline/aggregator.rs` | calibration + triangulation flags |
| `freemocap-rust/src/video_reader/mod.rs` | VideoGroup lifecycle |

### Open design questions for next session

1. **Stats collection**: Should PyPipeline collect and expose timing stats, or
   just discard them? The E2E test collects stats from JoinHandles — PyPipeline
   currently discards them via `{ fn(args); }` closures. (ANSWER - Print stats in terminal in nicely formated text block)

2. **Posthoc API shape**: Should posthoc be a separate `PyPosthocPipeline` class
   or a mode on PyPipeline (`source="video"` vs `source="camera"`)? The
   underlying Rust infrastructure is unified (Distributor checks
   `video_rx.is_some()`). (ANSWER - WE will match the current python api eventually, but thats not the focus right now)

3. **Calibration format**: Should Python pass a TOML file path (Rust parses it)
   or pre-parsed camera models (Python parses, passes dicts)? The Rust
   `calibration_loader` handles TOML parsing. Passing a path is simpler. (ANSWER - Pass a path, you idiot. Minimize python <-> Rust interaction)

4. **Error handling**: What happens when the Rust pipeline panics? PyO3 catches
   panics at the FFI boundary and converts them to Python exceptions, but the
   thread JoinHandles in PyPipeline's `Drop` impl need to handle poisoned
   mutexes gracefully.

## Quick Reference

```bash
cd C:\Users\jonma\code_repos\github\freemocap\freemocap\freemocap-rust

# Prerequisites (one-time):
#   vcpkg install opencv4[ffmpeg]:x64-windows-static --recurse

# Type checking
cargo check --lib

# All 11 tests (debug)
cargo test --lib

# E2E test with stats (release — for timing measurements)
cargo test --release --lib video_reader::pipeline_test -- --nocapture

# Check sibling crates
cd ../skellycam/skellycam-rust && cargo check --lib
cd ../../skellytracker/skellytracker-rust && cargo check --lib

# Build Python module (when ready)
cd ../../freemocap-rust && maturin develop
```

Test data: `C:\Users\jonma\freemocap_data\recordings\freemocap_test_data`
- 3 synchronized videos (222 frames, 720×1280, 6fps, mpeg4)
- Calibration TOML: `freemocap_test_data_camera_calibration.toml`
