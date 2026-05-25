# Timestamp Pipeline

> Worked example of Step 4 (Design Rust) — where the planned extensible timestamp system was simplified to a fixed struct. See the [re-architecture playbook](../rearchitecture-playbook/).

## The Problem

Record nanosecond-precision monotonic timestamps at every stage of the frame lifecycle. Compute durations between stages. Produce statistics for performance analysis.

### Invariants

- Per-frame timestamps on the camera thread
- Monotonic clock, immune to NTP slew and DST
- UTC mapping for correlation with external logs
- Framerate computation from consecutive frame timestamps
- Inter-camera sync measurement (arrival spread)

## Python's Solution

9 `time.perf_counter_ns()` call sites per frame:

```
initialized_ns           ← end of previous iteration
pre_frame_grab_ns        ← before cv2.VideoCapture.grab()
post_frame_grab_ns       ← after grab
pre_frame_retrieve_ns    ← before cv2.VideoCapture.retrieve()
post_frame_retrieve_ns   ← after retrieve (BGR decode)
pre_copy_to_camera_shm_ns ← before numpy copy to shared memory
post_copy_to_camera_shm_ns ← after SHM write
pre_frame_record_ns      ← before cv2.VideoWriter.write()
post_frame_record_ns     ← after write
```

Duration computation from these 9 yields 8 durations + total processing time. `TimebaseMapping` captured at startup maps `perf_counter_ns` to `utc_time_ns`.

### Python-Specific Decisions

| Mechanism | Why Python Needs It |
|-----------|-------------------|
| `time.perf_counter_ns()` returns raw i64 | Python's monotonic clock API returns integers |
| numpy recarray for structured timestamps | Python's only performant multi-dimensional array |
| `initialize_frame_recarray()` clears fields | In-place update pattern — must zero previous values |
| Fixed dtype (8 fields) — brittle to changes | Python has no `#[non_exhaustive]` for struct fields |

## Rust's Solution

### Performance Clock

Single T=0 anchor established at process start:

```rust
static ANCHOR: OnceLock<ClockAnchor> = OnceLock::new();

pub fn anchor_performance_clock() {
    ANCHOR.get_or_init(|| ClockAnchor {
        monotonic: Instant::now(),
        wall_clock: SystemTime::now(),
    });
}

pub fn performance_counter_nanoseconds() -> i64 {
    let anchor = ANCHOR.get(); // or lazy init
    anchor.monotonic.elapsed().as_nanos() as i64
}
```

All timestamps are nanoseconds since T=0. The wall-clock equivalent is captured for statistics headers. No `TimebaseMapping` struct needed.

### FrameLifecycleTimestamps (fixed struct, 5 fields)

```rust
pub struct FrameLifecycleTimestamps {
    pub loop_start_ns: i64,        // top of capture loop iteration
    pub frame_available_ns: i64,   // Cap_hasNewFrame() returned true
    pub post_jpeg_extract_ns: i64, // Cap_captureFrameRaw() + Vec copy
    pub pre_send_ns: i64,          // about to call frame_sender.send()
    pub gatherer_received_ns: i64, // stamped by gatherer after recv()
}
```

5 fields vs Python's 9. What was removed and why:
- `pre_grab` / `post_grab` — `openpnp-capture` doesn't expose grab/retrieve split
- `pre_retrieve` / `post_retrieve` — no BGR decode in hot path; `post_jpeg_extract` covers raw byte copy
- `pre_copy_to_shm` / `post_copy_to_shm` — no shared memory copy; threads share address space
- `initialized_ns` — not needed; iteration gap computed from consecutive `loop_start_ns`

### Gatherer Timestamps (separate struct)

```rust
pub struct GathererTimestamps {
    pub collecting_start_ns: i64,
    pub all_frames_received_ns: i64,
    pub post_barrier_ns: i64,
    pub payload_assembled_ns: i64,
    pub pre_send_downstream_ns: i64,
}
```

One set per multiframe cycle, populated by `GathererStateMachine` transitions.

### Statistics

Gatherer computes per-cycle and aggregate statistics on exit:
- Per-camera: wait for frame, JPEG extract, channel send wait, cycle total
- Multiframe-level: frame arrival spread, thread wakeup spread, FPS
- Gatherer-loop: frames collection, barrier wait, payload assembly, downstream send

All computed in pure Rust from `Vec<f64>` accumulators — no numpy, no Polars.

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Timestamp fields | 9 per frame | 5 per frame + 5 gatherer-level |
| Clock API | `time.perf_counter_ns()` (raw i64) | `Instant::elapsed().as_nanos()` (opaque origin, T=0 anchor) |
| UTC mapping | `TimebaseMapping` struct per group | `anchor_wall_clock_time()` from T=0 |
| Extensibility | Fixed numpy dtype (brittle) | Fixed struct (no extensibility layer built) |
| SHM copy timestamps | Present (~100μs of numpy memcpy) | Absent (no copy needed) |
| Decode timestamps | `pre_retrieve`/`post_retrieve` (BGR decode) | `post_jpeg_extract` (raw byte copy — ~10x faster) |
| Statistics | numpy double-loop per recording | Gatherer stats ring buffer (300 samples, warmup/cooldown gated) |
