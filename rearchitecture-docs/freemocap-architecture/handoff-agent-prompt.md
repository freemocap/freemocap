You're picking up work on the FreeMoCap Rust pipeline. The code is at
C:\Users\jonma\code_repos\github\freemocap\freemocap\freemocap-rust.

CRITICAL: DO NOT MAKE ASSUMPTIONS. DO NOT GUESS. DO NOT SKIM. You must actually
read the code files, read the rearchitecture docs, and trace the data flow
before you write a single line. The handoff doc is a MAP, not a replacement for
reading. Use it to know where to look, then go look.

## What's been built

Two major architectural changes landed in the last session:

### 1. Composable per-loop timestamp architecture

Every thread loop now gets its own `Timestamps` struct with named stage boundaries
and `end − start` duration helpers. `PipelineCycleTimestamps` composes
`DistributorTimestamps` + `HashMap<String, CameraNodeTimestamps>` +
`AggregatorTimestamps`. Each struct has duration methods (`slot_work_ns()`,
`triangulation_ns()`, etc.).

The same pattern was applied upstream in skellycam: `MultiFramePayload` now wraps
`GathererTimestamps` instead of carrying bare `i64` fields.

Key files:
- `freemocap-rust/src/pipeline/types.rs` — the four composable structs
- `skellycam-rust/src/camera/types.rs` — `MultiFramePayload` + `GathererTimestamps`

### 2. VideoGroup uses mpsc channel (not FrameSlots)

The video path no longer polls FrameSlots. The video dispatcher sends
`MultiFramePayload` (skellycam's type) on an unbounded mpsc channel. The
distributor receives via `recv()` — no pacing signal, no spin-waits, no
frame dropping. The distributor checks `video_rx.is_some()` to decide between
channel (video source) and FrameSlots (live camera source).

Key files:
- `freemocap-rust/src/video_reader/dispatcher.rs` — builds `MultiFramePayload`, sends on channel
- `freemocap-rust/src/video_reader/mod.rs` — VideoGroup lifecycle (open/start/shutdown)
- `freemocap-rust/src/video_reader/reader.rs` — single video file reader
- `freemocap-rust/src/pipeline/distributor.rs` — dual-source input (channel or FrameSlots)

### 3. Pipeline timing statistics

Per-stage, per-camera, per-thread timing block matching skellycam's gatherer
format (median/mean/std/CV%/min/max/n, per-camera breakdowns, mean/median camera
summaries, across-camera spread). All thread functions return their stats.

Key file:
- `freemocap-rust/src/pipeline/stats.rs` — stats accumulators + print formatting

## Before you do anything else, read ALL of these thoroughly:

1. **The handoff doc:**
   `rearchitecture-docs/freemocap-architecture/handoff-posthoc-pipeline.md` —
   explains what changed this session, current state, next steps, quick reference

2. **The architecture README:**
   `rearchitecture-docs/freemocap-architecture/README.md` —
   status table, design decisions, upstream changes

3. **All rearchitecture docs:**
   `rearchitecture-docs/freemocap-architecture/` — read every `0*.md` file.
   These document the design decisions and architecture patterns.

4. **The actual Rust source code — read every single file in these directories:**
   - `src/pipeline/` — distributor, camera_node, aggregator, types, config, stats
   - `src/triangulation/` — dlt, charuco, outlier_rejection, calibration_loader
   - `src/filtering/` — one_euro, velocity_gate, skeleton_filter
   - `src/video_reader/` — mod.rs, reader.rs, dispatcher.rs, pipeline_test.rs
   - `src/pipeline_manager/mod.rs`

5. **The skellycam-rust patterns to follow:**
   - `C:\Users\jonma\code_repos\github\freemocap\skellycam\skellycam-rust\src\camera\types.rs` —
     `MultiFramePayload`, `GathererTimestamps`, `FramePacket`, `FrameData`
   - `C:\Users\jonma\code_repos\github\freemocap\skellycam\skellycam-rust\src\camera_group\camera_group.rs` —
     `CameraGroup` lifecycle, `FrameSlots`, `GathererStateMachine`
   - `C:\Users\jonma\code_repos\github\freemocap\skellycam\skellycam-rust\src\camera_group\gatherer.rs` —
     how the gatherer produces `MultiFramePayload`
   - `C:\Users\jonma\code_repos\github\freemocap\skellycam\skellycam-rust\src\camera_group\dispatcher.rs` —
     how the dispatcher consumes `MultiFramePayload`

You need to actually understand:
- How `PipelineCycleTimestamps` composes the three per-loop timestamp structs
- How the distributor reads from either `mpsc::Receiver<MultiFramePayload>` (video) or `FrameSlots` (camera)
- How the video dispatcher builds `FramePacket`s and `MultiFramePayload`
- How the VideoGroup lifecycle works (open → start → take_video_receiver → shutdown)
- How camera nodes decode JPEG → detect charuco → send to aggregator
- How the aggregator collects, triangulates, filters, and publishes
- How the E2E test wires VideoGroup → channel → distributor → camera nodes → aggregator
- How the stats module accumulates per-stage timing and prints the statistics block

## Current state

11 tests pass:
```
cargo test --lib
```

E2E test (release build, 23.5 fps, 30 frames, 3 cameras, 720×1280):
```
cargo test --release --lib video_reader::pipeline_test -- --nocapture
```

Test data: `C:\Users\jonma\freemocap_data\recordings\freemocap_test_data`
- 3 synchronized videos (222 frames, 720×1280, 6fps, mpeg4)
- Calibration TOML: `freemocap_test_data_camera_calibration.toml`
- Pre-computed charuco observations: `output_data/charuco_observations.json`

Known bottleneck: `VideoCapture::read()` via `CAP_ANY` (MSMF backend) takes ~10ms
per 720×1280 frame. Switching to `CAP_FFMPEG` should improve this 3-5×.

## Next steps (prioritized)

### Immediate

1. **Fix video read performance**: Switch `VideoReader::open()` from `CAP_ANY` →
   `CAP_FFMPEG` in `src/video_reader/reader.rs`. This is a one-line change.

2. **Investigate charuco detection speed**: 24ms per camera vs 8ms expected in
   skellytracker webcam demo. Check resolution impact (720×1280 vs 640×480) and
   whether there's FFI overhead. The stats block already shows per-camera
   detection times — use that data.

3. **Build PosthocPipeline struct**: The E2E test manually wires VideoGroup →
   channel → pipeline. Extract this into a `PosthocPipeline` struct with a
   simple `run() -> PosthocResult` API. Add result export (JSON/CSV).

### Medium-term

4. `maturin develop` — build the `.pyd`, verify `import _freemocap_rust`
5. Batch triangulation mode for posthoc (collect all observations, triangulate once)
6. Skeleton inference (RTMPose)

### Later

7. Real-time server smoke test with live cameras
8. FABRIK skeleton constraint filter

## Guardrails

- Do NOT touch the server code, the PyO3 bridge, or skeleton_filter unless
  unavoidable. Focus on the core pipeline and video_reader modules.
- When changing thread function signatures, wrap the call in `py_pipeline.rs`
  with a closure that discards the return value (`{ fn(args); }`).
- Prefer editing existing files over creating new ones.
- Run `cargo check --tests` after every change. Run `cargo test --lib` before
  claiming completion.
- If you change anything in skellycam (sibling crate), check both:
  `cd ../skellycam/skellycam-rust && cargo check --lib`
