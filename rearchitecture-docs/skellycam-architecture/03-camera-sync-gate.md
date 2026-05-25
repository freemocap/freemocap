# Camera Sync Gate and Capture Loop

> Worked example of Step 1 (Understand) + Step 4 (Design Rust) — the component where the architecture diverged most dramatically from Python. See the [re-architecture playbook](../rearchitecture-playbook/).

## The Problem

Multiple cameras must capture frames in lockstep — no camera gets more than 1 frame ahead of any other. Per-frame timestamps must be recorded for performance analysis. The capture loop is the hot path and must be protected from everything else.

### Invariants

- All cameras at the same frame number before a multiframe is emitted
- Per-frame timestamps for performance measurement
- Pause must stop frame capture without dropping camera connections
- Config changes must apply mid-stream without stopping capture
- Camera error must not go unnoticed

## Python's Solution

`CameraOrchestrator.should_grab_by_id()` — a polling-based sync gate:

```python
def should_grab_by_id(self, camera_id) -> bool:
    if not self.all_ready:
        return False
    return self._all_camera_counts_greater_than_or_equal_to_camera(camera_id)

def _all_camera_counts_greater_than_or_equal_to_camera(self, camera_id):
    counts = deepcopy(self.camera_frame_counts)  # snapshot from shared memory
    return all(counts[camera_id] <= count for count in counts.values())
```

Each camera polls `should_grab_by_id()` in a loop spinning at 10μs. Only proceeds when its frame count ≤ all others' counts. `frame_count` is a `multiprocessing.Value("q")` in shared memory.

**11 `CameraStatus` flags** per camera: `connected`, `grabbing_frame`, `recording_in_progress`, `is_recording_frame`, `is_paused`, `should_pause`, `should_close`, `closing`, `closed`, `updating`, `error` — all `multiprocessing.Value("b")`.

**Capture**: OpenCV `VideoCapture.grab()` + `.retrieve()` with four timestamps (pre/post grab, pre/post retrieve). BGR decode happens on the camera thread.

### Python-Specific Decisions

| Mechanism | Why Python Needs It |
|-----------|-------------------|
| `should_grab_by_id()` polling at 10μs | No blocking sync primitive across processes |
| `deepcopy(self.camera_frame_counts)` | Must snapshot all shared counters atomically |
| 11 `multiprocessing.Value` booleans | Each flag is a separate cross-process shared value |
| OpenCV grab/retrieve split | Pre-allocated numpy array avoids allocation in hot loop |
| `check_framerate_reset()` | USB cameras enter degraded state; recreating VideoCapture recovers |

## Rust's Solution

### Capture API: openpnp-capture FFI

Uses `openpnp-capture` C library (DirectShow FFI) instead of OpenCV:
- `Cap_hasNewFrame()` — poll for available frame
- `Cap_getFrameSize()` + `Cap_captureFrameRaw()` — copy raw MJPEG bytes
- **No BGR decode** in the hot path — MJPEG bytes flow through unchanged
- COM context is thread-affine (same constraint as OpenCV)

### Sync Mechanism: BreakableBarrier

The planned "structural backpressure" was prototyped but a `BreakableBarrier` proved simpler to debug:

```
Camera thread (per camera):        Gatherer thread:
  Cap_hasNewFrame() spin
  Cap_captureFrameRaw() → MJPEG
  frame_sender.send(packet) ────→  recv() from each camera ← BLOCKS
  barrier.wait() ← BLOCKS ───────  barrier.wait() ← rendezvous
    ↓ (all release together)         ↓
  begin next capture               assemble MultiFramePayload
```

After sending, cameras block at the barrier. The gatherer collects frames then arrives at the same barrier. All threads release simultaneously.

### Camera Capture Loop

```
1. Check command channel (try_recv) — Shutdown/Configure
2. If paused: spin-wait checking commands, sleep 1ms
3. Spin on Cap_hasNewFrame() (yield_now, 5s timeout)
4. Stamp frame_available_ns
5. Cap_getFrameSize() → resize buffer if needed
6. Cap_captureFrameRaw() → copy MJPEG bytes (retry up to 3x)
7. Stamp post_jpeg_extract_ns
8. Build FramePacket, stamp pre_send_ns
9. frame_sender.send(packet)  [sync_channel(1)]
10. barrier.wait() ← synchronizes all cameras + gatherer
11. Stamp loop_start_ns for next iteration
12. Increment frame_number
```

### CameraStatus — collapsed

Python's 11 flags become:
- `paused: Arc<AtomicBool>` — replaces `is_paused`, `should_pause`, `should_close`
- Camera events via `mpsc::channel` — replaces `connected`, `error`, `closing`, `closed`
- No individual `grabbing_frame`, `is_recording_frame`, `recording_in_progress` flags

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Sync mechanism | `should_grab_by_id()` polling + atomics | `BreakableBarrier` rendezvous |
| Camera API | OpenCV `VideoCapture` (grab/retrieve) | `openpnp-capture` FFI (raw MJPEG) |
| Image format in pipeline | BGR (decoded from MJPEG) | MJPEG (passthrough, no decode) |
| Frame pacing | `sync_channel(1)` backpressure was planned | Actually: `sync_channel(1)` + barrier |
| Status flags | 11 `multiprocessing.Value` booleans | 1 `Arc<AtomicBool>` + event channel |
| Config mid-stream | PubSub broadcast + polling | Direct `TryRecv` at loop top |
| Degraded camera recovery | `check_framerate_reset()` recreates VideoCapture | Not observed as necessary with raw DirectShow |
