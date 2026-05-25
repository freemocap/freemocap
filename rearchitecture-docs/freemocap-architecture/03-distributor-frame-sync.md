# Distributor & Frame Sync

> Step 4 (Design Rust Architecture) — where the inverted BreakableBarrier pattern ensures synchronized multi-consumer fan-out.

## The Problem

Move the latest multi-camera frames from skellycam into the pipeline's camera nodes. All camera nodes must receive the same frame number. The distributor must never overwrite frames while cameras are reading. The frontend payload (pre-encoded JPEGs) must be captured at the same moment as the raw frames so the final output is self-consistent.

### Invariants

- All camera nodes always process the same frame number — desync by even one frame is a full failure
- Distributor drops intermediate frames when pipeline is slower than cameras
- Frontend payload is bundled with the frame it belongs to at capture time
- Distributor never blocks on camera node completion (barrier is the only sync point)

## Python's Solution

The Python pipeline has no distributor. Instead, the `AggregatorNode`:
1. Checks `camera_group_shm.latest_multiframe_number`
2. If newer than `latest_requested_frame` AND `result_consumed_event` is set, publishes `ProcessFrameNumberMessage(frame_number=N)` via PubSub
3. Each `CameraNode` receives the message, reads frame N from its camera's SHM ring buffer
4. Camera nodes publish `CameraNodeOutputMessage` via PubSub
5. Aggregator collects outputs, verifies all at same frame_number

Frame pacing is pull-based with backpressure via `multiprocessing.Event`. No barrier — camera nodes are independent processes that happen to receive the same frame number request.

## Rust's Solution

### Architecture

```
Distributor (thread):
  loop {
    // 1. Atomically snapshot BOTH slots from skellycam
    let raw = camera_group.latest_raw_frames();
    let payload = camera_group.latest_frontend_payload();

    // 2. Guard: dispatcher might have been mid-update
    if raw.is_none() || payload.is_none() { continue; }
    if raw.frame_number != payload.frame_number { continue; }

    // 3. Only push if there's a new frame
    if raw.frame_number <= last_distributed { continue; }

    // 4. Write shared slot under exclusive lock
    {
      let mut slot = shared_slot.write();
      slot.frame_number = raw.frame_number;
      slot.per_camera_jpegs = raw.frames.clone();    // one clone per cycle
      slot.frontend_payload = payload.jpeg_bytes.clone();
    }

    // 5. Release all camera nodes simultaneously
    if !barrier.wait() { break; }  // false = barrier broken (shutdown)

    last_distributed = raw.frame_number;
  }
```

### Implemented approach: Direct Arc polling (zero Python)

The distributor holds `FrameSlots` — clones of the same `Arc<Mutex<Option<T>>>` that the skellycam dispatcher writes to. It polls them directly in Rust:

```rust
// In the distributor loop:
let raw_frames = {
    let guard = distributor.frame_slots.raw_frames.lock().unwrap();
    guard.clone()
};
let frontend_payload = {
    let guard = distributor.frame_slots.frontend_payload.lock().unwrap();
    guard.clone()
};
```

Zero Python in the frame path. JPEG bytes stay in Rust heap from camera capture through detection to output. The `FrameSlots` are extracted from the skellycam `PyO3CameraGroupManager` at pipeline construction time (Rust-to-Rust, via the pyclass borrow).

### BreakableBarrier (reused from skellycam)

```rust
pub struct BreakableBarrier { ... }
impl BreakableBarrier {
    pub fn new(total: usize) -> Self;
    pub fn wait(&self) -> bool;         // true = normal, false = barrier broken
    pub fn break_barrier(&self);        // release all waiters (shutdown)
    pub fn set_total(&self, n: usize);  // dynamic add/remove cameras
}
```

Constructed with `N_cameras + 1` (one per camera + distributor). Each cycle:
1. Distributor writes shared slot, calls `barrier.wait()` → blocks
2. All camera nodes are also blocked at `barrier.wait()`
3. When all N+1 parties have arrived, barrier releases everyone simultaneously
4. Camera nodes read their respective frames from the shared slot
5. Distributor loops back to poll for the next frame

The slot is guaranteed stable during reads because the distributor is blocked at the barrier — it can't write again until cameras finish processing and re-enter the barrier.

### Frontend Payload Bundling

The distributor captures `latest_frontend_payload` in the same critical section as `latest_raw_frames`. The payload bytes ride through the pipeline untouched:

```
Distributor captures:  { frame_n: 42, jpegs: [...], payload: <bin> }
    → Camera nodes read jpegs, ignore payload
    → Aggregator collects outputs, bundles payload into AggregatorOutput
    → WebSocket relay reads AggregatorOutput, sends payload + keypoints together
```

No separate frame number lookup. No possibility of mismatch.

### Frame Dropping

If the pipeline takes 50ms per cycle and cameras produce at 33ms (30fps):

```
Camera frames:   [40] [41] [42] [43] [44] [45] ...
                   │         │         │
Distributor polls:  ▼         ▼         ▼
                 grabs 40   grabs 42   grabs 44
                 (41 skipped — was overwritten during processing)
```

The distributor only sees the latest frame in the slot. Intermediate frames are naturally dropped.

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Frame distribution | Pull-based: aggregator publishes frame number request | Push-based: distributor writes slot, barrier releases |
| Sync mechanism | Independent processes polling queue | BreakableBarrier rendezvous |
| Backpressure | `multiprocessing.Event` pair | Barrier naturally paces — distributor can't get ahead |
| Frontend payload pairing | Separate lookup by frame_number in SHM | Captured atomically with raw frames |
| Frame dropping | Aggregator skips `process_frame_number_pub` when busy | Distributor only checks slot when ready |
| Shared state | Per-camera SHM ring buffers (N regions, N DTOs) | One `RwLock<DistributorSlot>` |
