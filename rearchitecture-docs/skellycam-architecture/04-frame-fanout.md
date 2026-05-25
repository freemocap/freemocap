# Frame Fan-Out: Gatherer to Frontend and Recorder

> Worked example of Step 4 (Design Rust) + Step 5 (Patterns) — where Python's ring buffer architecture was replaced with a dispatcher-based fan-out. See the [re-architecture playbook](../rearchitecture-playbook/).

## The Problem

After the gatherer assembles a `MultiFramePayload` (one frame from each camera at the same frame number), it must be delivered to multiple consumers:
- **Frontend (WebSocket)**: latest frame only, as fast as possible, non-blocking for producer
- **Recorder**: every frame, in order, never dropped

### Invariants

- Exact binary protocol layout for frontend (PayloadHeader 24 bytes, FrameHeader 56 bytes, `#[repr(C)]`)
- Recorder sees every frame — no drops
- Frontend sees latest only — no blocking the gatherer
- Binary protocol message types: 0 (header), 1 (frame), 2 (footer)

## Python's Solution

Per-camera `SharedMemory` ring buffers with two cursors (`last_written_index`, `last_read_index`). The `CameraGroupSharedMemory.get_latest_multiframe()` method reads the latest frame from each camera's ring buffer, validates all at the same frame number, then passes to `create_frontend_payload()`:

1. Compute grab timestamp midpoint: `mean(pre_grab_ns, post_grab_ns)`
2. Rotate image via `cv2.rotate()`
3. Resize to 50% via `cv2.resize(INTER_LINEAR)`
4. JPEG encode at quality 80 via `cv2.imencode('.jpg')`
5. Assemble header + per-camera headers + JPEG bytes + footer into reusable bytearray

### Python-Specific Decisions

| Mechanism | Why Python Needs It |
|-----------|-------------------|
| Shared memory ring buffers | Frames are multi-MB — can't copy through pipes between processes |
| Two cursors per ring buffer | Producer and consumer are in different processes |
| `overwrite_allowed=True` | Streaming consumer must never block camera producer |
| Reusable global bytearray | Avoids GC pauses in streaming loop |
| `asyncio.Lock` for WebSocket writes | `websockets` library doesn't support concurrent writes |

## Rust's Solution

### Dispatcher-Based Fan-Out

The planned "gatherer → broadcast fan-out with `watch`/`mpsc`" was simplified to a dispatcher thread:

```
Gatherer ──unbounded mpsc──→ Dispatcher ──┐
                                │          ├── Arc<Mutex<Option<FrontendPayload>>>  ← WS polls
                                │          └── Recording thread (via channel)        ← only when recording
```

The dispatcher `try_recv()`s from the gatherer (never blocking), encodes the frontend payload, stores it, and forwards to the recording thread if active.

### Binary Protocol (Matches Python Bit-for-Bit)

```rust
#[repr(C)]
pub struct PayloadHeader {       // 24 bytes
    pub message_type: u8,        // 0 = header, 2 = footer
    _padding1: [u8; 7],
    pub frame_number: i64,
    pub number_of_cameras: i32,
    _padding2: [u8; 4],
}

#[repr(C)]
pub struct FrameHeader {         // 56 bytes
    pub message_type: u8,        // always 1
    _padding1: [u8; 7],
    pub frame_number: i64,
    pub camera_identifier: [u8; 16],
    pub camera_index: i32,
    pub image_width: i32,
    pub image_height: i32,
    pub color_channels: i32,
    pub jpeg_string_length: i32,
    _padding2: [u8; 4],
}
```

### MJPEG Passthrough (Not Decode→Re-encode)

The planned "decode BGR → rotate → resize 50% → JPEG encode at quality 80" is NOT used for MJPEG frames. Instead:
- **MJPEG frames pass through as raw bytes** — no decode, no resize, no re-encode
- Only lossless JPEG rotation is applied via turbojpeg `tjTransform` in the dispatcher
- The RGB path exists only as a fallback for non-MJPEG cameras

### WebSocket: Polling, Not Watch

No `tokio::sync::watch`. The WebSocket loop polls `CameraGroup::latest_frontend_payload()` every 10ms:

```rust
loop {
    let payload = manager.get_group(group_id)
        .and_then(|g| g.latest_frontend_payload());
    if let Some(payload) = payload {
        if payload.frame_number > last_frame_number {
            socket.send(Message::Binary(payload.jpeg_bytes.into())).await?;
        }
    }
    tokio::time::sleep(Duration::from_millis(10)).await;
}
```

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Frame buffering | Shared memory ring buffers | Heap `Vec<u8>` via channels + shared slots |
| Fan-out topology | SHM → multi-consumer reads | Gatherer → Dispatcher → downstream consumers |
| Image processing | BGR decode → rotate → resize 50% → JPEG Q80 | MJPEG passthrough + lossless rotation only |
| WebSocket delivery | `asyncio.Lock` serialized writes | `split()` gives independent send/receive halves |
| Flow control | `frameNumber` acks from frontend | TCP backpressure only |
| Bytearray reuse | Module-level global reusable bytearray | `Vec<u8>` with `clear()` — no global state |
