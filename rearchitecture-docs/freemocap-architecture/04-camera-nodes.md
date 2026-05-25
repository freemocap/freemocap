# Camera Nodes

> Step 4 (Design Rust Architecture) — per-camera detection threads using skellytracker's CharucoTracker.

## The Problem

Each camera node receives a JPEG frame from the distributor, decodes it to BGR, runs charuco detection, and sends the observation downstream to the aggregator. Detection is CPU-bound and runs in parallel across N threads (one per camera).

### Invariants

- All camera nodes process the same frame_number
- JPEG decode happens here (unavoidable — charuco detection needs pixel data)
- Detection uses skellytracker-rust's `CharucoTracker` (already built)
- Camera node must never block the distributor
- Config updates (charuco board params) apply mid-stream without restart

## Python's Solution

Each `CameraNode` is a `multiprocessing.Process`:
- Reads frame from per-camera `SharedMemory` ring buffer
- Optional BGR rotation via `cv2.rotate()`
- Runs `CharucoDetector.detect()` and/or `RTMPoseDetector.detect()`
- Publishes `CameraNodeOutputMessage` via PubSub
- Config updates arrive via `PipelineConfigUpdateTopic` subscription (polled at loop top)

## Rust's Solution

### Camera Node Thread

```rust
fn camera_node_loop(
    camera_id: CameraId,
    barrier: Arc<BreakableBarrier>,
    shared_slot: Arc<RwLock<DistributorSlot>>,
    cmd_rx: mpsc::Receiver<PipelineCommand>,
    output_tx: mpsc::Sender<CameraNodeOutput>,
) {
    let mut detector = CharucoTracker::default(); // or from initial config

    loop {
        // ── Handle commands (non-blocking) ──
        match cmd_rx.try_recv() {
            Ok(PipelineCommand::UpdateConfig(config)) => {
                detector = CharucoTracker::from_config(&config.charuco_config);
            }
            Ok(PipelineCommand::Shutdown) => break,
            Err(TryRecvError::Empty) => {}
            Err(TryRecvError::Disconnected) => break,
        }

        // ── Synchronize with distributor ──
        if !barrier.wait() { break; }  // false = barrier broken

        // ── Read frame from shared slot (distributor is blocked at barrier) ──
        let (frame_number, jpeg_bytes) = {
            let slot = shared_slot.read();
            (slot.frame_number, slot.per_camera_jpegs[camera_id].clone())
        };

        // ── Decode JPEG → BGR ──
        let image = match imgcodecs::imdecode(&jpeg_bytes, imgcodecs::IMREAD_COLOR) {
            Ok(img) => img,
            Err(e) => {
                eprintln!("[freemocap] CameraNode[{camera_id}]: JPEG decode failed: {e}");
                continue;
            }
        };

        // ── Charuco detection ──
        let observation = match detector.process_image(frame_number, &image) {
            Ok(obs) => obs,
            Err(e) => {
                eprintln!("[freemocap] CameraNode[{camera_id}]: detection error: {e}");
                Box::new(CharucoObservation::empty(frame_number))
            }
        };

        // ── Send downstream ──
        output_tx.send(CameraNodeOutput {
            camera_id,
            frame_number,
            observation,
        }).unwrap_or_else(|_| break); // aggregator disconnected = shutdown
    }
}
```

Key points:
- `barrier.wait()` blocks until distributor writes the slot and all cameras arrive
- After barrier release, ALL cameras read from the same slot under a shared read lock — concurrent reads, no contention
- `cmd_rx.try_recv()` at loop top gives zero-latency command processing
- JPEG decode is unavoidable here — charuco detection needs pixel data
- `continue` on decode failure (skip this frame, don't crash the thread)
- Channel disconnect on `output_tx.send()` triggers clean exit (aggregator shut down)

### What's Not Here (Yet)

- **Skeleton detection** — deferred. Will be added as an optional second detector call after charuco, or as a separate centralized GPU inference node.
- **Image rotation** — skellycam already applies lossless JPEG rotation in the dispatcher. Camera nodes receive correctly oriented frames.
- **Per-frame timing** — `FrameLifecycleTimestamps` can be added using skellycam's performance clock.

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Process model | `multiprocessing.Process` | `std::thread::spawn` |
| Frame source | SHM ring buffer (DTO recreate) | `Arc<RwLock<DistributorSlot>>` (shared heap) |
| Sync | `ProcessFrameNumberMessage` via PubSub queue | `BreakableBarrier` rendezvous |
| Config updates | PubSub subscription polling | Direct `mpsc::Receiver<PipelineCommand>` |
| Detection | `CharucoDetector.detect()` (Python) | `CharucoTracker::process_image()` (Rust) |
| Error handling | Exception → `kill_everything()` | `eprintln!` + `continue` (skip frame) |
