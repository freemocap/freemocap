# Recording Pipeline

> Worked example of Step 1 (Understand) + Step 4 (Design Rust) from the [re-architecture playbook](../rearchitecture-playbook/).

## The Problem

Record synchronized multi-camera video to disk. Each camera gets its own video file with consistent naming. Per-frame timestamps and metadata are collected for post-recording analysis.

### Invariants

- Per-camera video files: `Camera_{index}_{id}_{label}.mp4`
- Recording folder schema: `synchronized_videos/` and `timestamps/` subdirectories
- Frame metadata collected during recording
- Clean finalization even if recording is interrupted

## Python's Solution

Per-camera `VideoRecorder` wrapping OpenCV's `cv2.VideoWriter`. The pause-before-record protocol coordinates boundaries across processes:

**Start recording**: pause all cameras → set `first_recording_frame_number = current + 3` → publish `RecordingInfoMessage` via PubSub → unpause

**Stop recording**: pause all cameras → set `last_recording_frame_number = current + 3` → unpause → wait for `RecordingFinishedMessage` from each camera via PubSub → `RecordingFinalizer.finalize_recording()`

**Timestamp pipeline**: numpy recarray per frame with 9 timestamp fields. Duration computation via manual double-loop over (num_cameras, num_frames). CSV output to per-camera and multiframe files.

### Python-Specific Decisions

| Mechanism | Why Python Needs It |
|-----------|-------------------|
| `cv2.VideoWriter` per camera in camera process | Writer must be in same process as camera (GIL/context) |
| Pause-before-record with +3 offset | Recording boundaries communicated via shared `Value("q")` |
| `RecordingFinishedMessage` via PubSub | Camera process owns metadata; must serialize to main process |
| `await await_1ms()` during duration computation | Prevents asyncio event loop starvation |
| numpy recarray for structured timestamps | Python's only performant multi-dimensional array |

## Rust's Solution

### ffmpeg Subprocess per Camera

```rust
pub struct VideoRecorder {
    child: Child,
    stdin: Option<ChildStdin>,
    frame_count: u64,
}
```

- `start(width, height, fps, output_path)` — spawns ffmpeg with `-f rawvideo -pixel_format rgb24`
- `feed_frame(rgb_data)` — writes raw bytes to stdin (blocking if ffmpeg is slow)
- `finish()` — drops stdin (EOF), waits for ffmpeg exit
- `Drop` — kills ffmpeg if `finish()` was never called

MJPEG→RGB decode happens on the recording thread, not on the camera or dispatcher threads.

### Recording Architecture

Recording is managed by a dedicated thread spawned by the dispatcher:

1. `CameraGroup::start_recording(params)` → dispatcher builds `RecorderSpawnConfig` per camera
2. Dispatcher spawns recording thread via `spawn_recording_thread()`
3. Each multiframe, dispatcher sends `RecordingFrameData` (JPEG bytes + timestamps) to recording thread
4. Recording thread decodes JPEG→RGB, feeds ffmpeg, collects metadata
5. `stop_recording()` → dispatcher tells recording thread to finalize
6. Recording thread finishes all recorders, returns `RecordingSummary` via oneshot channel

### No Pause-Before-Record Protocol

Recording starts and stops on-the-fly. The first frame after `StartRecording` is recorded; the last frame before `StopRecording` is the final frame. No `first_recording_frame_number` / `last_recording_frame_number` atomics. No +3 offset.

### RecordingStats

```rust
pub struct RecordingStats {
    frame_avail_ns_per_camera: Vec<Vec<i64>>,
    post_encode_ns_per_multiframe: Vec<i64>,
    frame_counts_per_camera: Vec<usize>,
    start_ns: i64,
    end_ns: i64,
}
```

`push_multiframe(payload, post_encode_ns)` called by dispatcher each multiframe while recording. `finalize()` returns collected data.

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Video encoder | `cv2.VideoWriter` (OpenCV) | ffmpeg subprocess (stdin pipe) |
| Recording start | Pause → set boundaries → unpause | On-the-fly via dispatcher command |
| Frame offset | +3 frame offset for boundary visibility | None — no pause protocol |
| Timestamp recording | numpy recarray, 9 fields per frame | `RecordingStats` with per-camera Vecs |
| Finalization | Async PubSub wait for all cameras | Sync on recording thread, oneshot response |
| CSV output | Per-camera + multiframe CSVs with 15+ columns | `CsvWriter` exists but not wired in (deferred) |
| Analysis | numpy duration computation | Polars integration deferred |
