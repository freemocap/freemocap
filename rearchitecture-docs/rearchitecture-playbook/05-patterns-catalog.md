# Step 5: Patterns Catalog

Reusable Rust patterns that emerged from the skellycam re-architecture. These are solutions to problems that appear across multiple FreeMoCap components.

Each pattern includes: the problem it solves, why it works in Rust, a code sketch, where it's used in skellycam, and when to apply it elsewhere.

## Pattern: BreakableBarrier for Multi-Thread Synchronization

**Problem**: N camera threads must produce frames in lockstep — no camera gets more than 1 frame ahead of any other. Python solves this with `should_grab_by_id()` polling. In Rust, we can do better.

**Solution**: A `BreakableBarrier` that N camera threads + 1 gatherer thread rendezvous at each cycle. After sending its frame, each camera calls `barrier.wait()` and blocks until all cameras AND the gatherer have arrived. The barrier releases all threads simultaneously.

**Why it works**: Barriers are a classic concurrency primitive. The twist is making it "breakable" — when shutdown is requested, `break_barrier()` releases all waiters with a `false` return value so they know to exit rather than continue.

**Sketch**:
```rust
pub struct BreakableBarrier {
    total: AtomicUsize,
    arrived: AtomicUsize,
    // ... condvar + mutex for blocking
}

impl BreakableBarrier {
    pub fn new(total: usize) -> Self;
    pub fn wait(&self) -> bool;        // true = normal, false = barrier broken
    pub fn break_barrier(&self);       // release all waiters
    pub fn set_total(&self, n: usize); // dynamic add/remove cameras
}
```

**Used in**: `camera_group::sync_utils::BreakableBarrier`

**Apply when**: You have multiple threads performing the same work cycle that must stay synchronized. Also useful when the participant count changes dynamically (cameras added/removed).

## Pattern: MJPEG Passthrough

**Problem**: Python decodes MJPEG→BGR, rotates, resizes to 50%, and JPEG re-encodes every frame before sending to the frontend. This decode+re-encode costs several milliseconds per frame per camera.

**Solution**: Cameras produce MJPEG natively. Don't decode. The JPEG bytes flow through the entire pipeline unchanged. Only apply lossless rotation (turbojpeg `tjTransform`) in the dispatcher. The frontend receives the camera's original JPEG bytes at native resolution.

**Why it works**: Webcams encode MJPEG in hardware. Decoding to BGR and re-encoding to JPEG is pure waste if you're just forwarding to a browser (which decodes JPEG for display anyway). Lossless JPEG rotation operates on the DCT coefficients directly — no decode/re-encode.

**Sketch**:
```rust
fn rotate_jpeg_lossless(jpeg_bytes: &[u8], rotation: i32) -> Option<Vec<u8>> {
    // turbojpeg tjTransform — O(1) memory, DCT-domain rotation
}
```

**Used in**: `camera_group::jpeg_transform::rotate_jpeg_lossless`, `camera_group::frontend_encoder::encode_multiframe`

**Apply when**: Any pipeline that captures MJPEG from hardware and forwards to a consumer that can decode JPEG. The key insight: don't decode unless you need to modify pixels.

## Pattern: Arc<Mutex<Option<T>>> for Polling-Based State Sharing

**Problem**: The WebSocket handler needs the latest frontend payload, but it runs in a tokio task while the dispatcher runs in an OS thread. The dispatcher must never block, and the WebSocket handler must never miss an update by blocking on a lock held by the dispatcher.

**Solution**: A shared `Arc<Mutex<Option<FrontendPayload>>>`. The dispatcher acquires the lock, replaces the `Option` with `Some(new_payload)`, releases. The WebSocket handler acquires the lock, clones the payload, releases. Both hold the lock for microseconds — just long enough to swap/clone the `Option`.

**Why it works**: The critical section is a pointer swap. No channel overhead, no allocation in the hot path. The `Option` lets the consumer detect "no payload yet" vs "same payload as before."

**Sketch**:
```rust
// Writer (dispatcher thread):
if let Ok(mut guard) = latest_payload.lock() {
    *guard = Some(FrontendPayload { ... });
}

// Reader (WebSocket task):
let payload = manager.get_group(id)
    .and_then(|g| g.latest_frontend_payload()); // clone
if let Some(payload) = payload {
    if payload.frame_number > last_frame_number {
        socket.send(Message::Binary(payload.jpeg_bytes.into())).await?;
    }
}
```

**Used in**: `CameraGroup` fields: `latest_frontend_payload`, `latest_raw_frames`, `performance_snapshot`

**Apply when**: A producer updates state at high frequency and a consumer polls at a lower frequency. Works best when the shared data is cheap to clone (a few KB of bytes, not multi-MB frames).

## Pattern: Channel Command Dispatch

**Problem**: Running camera threads need to receive configuration changes, shutdown signals, and other commands without polling or interrupting the capture loop.

**Solution**: Each camera thread owns an `mpsc::Receiver<CameraCommand>`. The camera loop calls `try_recv()` at the top of each iteration. Commands that arrive between iterations are processed before the next frame capture. `tokio::select!` is not used because camera threads are OS threads, not async tasks.

**Sketch**:
```rust
enum CameraCommand {
    Shutdown,
    Configure { config: CameraConfig },
}

// Camera loop:
loop {
    match command_receiver.try_recv() {
        Ok(CameraCommand::Shutdown) => break,
        Ok(CameraCommand::Configure { config }) => { apply_config(config); }
        Err(TryRecvError::Empty) => {}
        Err(TryRecvError::Disconnected) => break,
    }
    // ... capture frame ...
}
```

**Used in**: `Camera::configure()`, `Camera::shutdown()`, `DispatcherCommand` for recording control, `GathererUpdate` for dynamic camera set changes

**Apply when**: Any long-running thread needs to receive sporadic commands without blocking its main loop. `try_recv()` gives zero-latency command processing when commands are pending and zero overhead when they're not.

## Pattern: Drop-Based Cleanup

**Problem**: Python needs `atexit` handlers, `try/finally` blocks, context managers, and 3-phase escalating shutdown to ensure resources are freed. In Rust, `Drop` handles this deterministically.

**Solution**: Every resource that needs cleanup gets a `Drop` impl. When a `Camera` is dropped, the thread is detached (or joined). When a `CameraGroupManager` is dropped, all groups are shut down. When a `VideoRecorder` is dropped without `finish()`, ffmpeg is killed. The compiler guarantees these run — even on panic.

**Sketch**:
```rust
impl Drop for CameraGroupManager {
    fn drop(&mut self) {
        if !self.groups.is_empty() {
            tracing::warn!("CameraGroupManager dropped with active groups — shutting down");
            self.close_all_groups();
        }
    }
}

impl Drop for VideoRecorder {
    fn drop(&mut self) {
        // kill ffmpeg if finish() was never called
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
        }
    }
}
```

**Used in**: `CameraGroupManager::Drop`, `VideoRecorder::Drop`, channel `Sender` drops that unblock `Receiver`s

**Apply when**: Any resource that must be freed on scope exit. Thread handles, subprocesses, file handles, channel senders. `Drop` is Rust's universal cleanup mechanism.

## Pattern: Unbounded Channel for Gatherer Output

**Problem**: The gatherer thread holds the barrier — every camera is waiting for it. If the gatherer blocks on a channel send, all cameras stall. But the consumer (dispatcher) might be busy encoding the previous payload.

**Solution**: Use an unbounded `mpsc::channel()` from gatherer to dispatcher. The gatherer's `send()` never blocks. The dispatcher uses `try_recv()` to drain frames as fast as it can. If the dispatcher falls behind, the channel buffers frames in memory — bounded only by available RAM, which is fine because the dispatcher is fast.

**Why it works**: The gatherer's cycle time is bounded by the slowest camera (typically 33ms at 30fps). The dispatcher's encoding time is a few hundred microseconds. The dispatcher keeps up easily, so the unbounded channel never grows beyond 1-2 frames. But if the dispatcher DOES stall, we'd rather buffer a few frames than drop them or block the gatherer.

**Sketch**:
```rust
let (multi_frame_sender, multi_frame_receiver) = mpsc::channel(); // unbounded

// Gatherer:
multi_frame_sender.send(payload).unwrap(); // never blocks

// Dispatcher:
match multi_frame_receiver.try_recv() {
    Ok(payload) => { /* encode + store */ }
    Err(TryRecvError::Empty) => { /* sleep 1ms */ }
    Err(TryRecvError::Disconnected) => { /* shutdown */ }
}
```

**Used in**: `CameraGroup::start()` — the gatherer → dispatcher channel

**Apply when**: A producer thread must never block, and the consumer can keep up in steady state. Use `sync_channel(n)` instead when you want backpressure (like camera → gatherer, where capacity 1 gives implicit frame pacing).

## Pattern: T=0 Performance Clock Anchor

**Problem**: All timestamps in the system must be comparable. Python uses `time.perf_counter_ns()` which returns an arbitrary int64. In Rust, `std::time::Instant` is opaque — you can't convert it to/from integers.

**Solution**: Establish a single `T=0` anchor at process start. All timestamps are nanoseconds since that anchor, measured by `Instant::elapsed().as_nanos()`. Capture the wall-clock equivalent of T=0 for correlation with external logs.

**Sketch**:
```rust
static ANCHOR: OnceLock<ClockAnchor> = OnceLock::new();

struct ClockAnchor {
    monotonic: Instant,
    wall_clock: SystemTime,
}

pub fn anchor_performance_clock() {
    ANCHOR.get_or_init(|| ClockAnchor {
        monotonic: Instant::now(),
        wall_clock: SystemTime::now(),
    });
}

pub fn performance_counter_nanoseconds() -> i64 {
    let anchor = ANCHOR.get_or_init(/* lazy init if needed */);
    anchor.monotonic.elapsed().as_nanos() as i64
}
```

**Used in**: `timestamps::performance` — called once from `init_logging()`, then every frame from camera threads and gatherer

**Apply when**: Any system that needs monotonic, cross-thread comparable timestamps with UTC mapping. The key property: one anchor, many readers, zero contention.
