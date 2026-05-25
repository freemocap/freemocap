# WebSocket Binary Protocol

> Worked example of Step 2 (Extract Invariants) — the binary protocol is the most rigid invariant in the entire system. See the [re-architecture playbook](../rearchitecture-playbook/).

## The Problem

Deliver multi-camera frames to the frontend via WebSocket in a binary format the frontend JavaScript can parse. The byte layout must match the Python implementation bit-for-bit.

### Invariants

- `PayloadHeader`: 24 bytes, `message_type` at offset 0 (0 = header, 2 = footer)
- `FrameHeader`: 56 bytes, `message_type` = 1, `camera_identifier` fixed 16 bytes
- All integers little-endian
- `#[repr(C)]` layout matching Python numpy dtypes with `align=True`
- JPEG bytes follow each FrameHeader
- Footer validates message completeness

## Binary Wire Format

```
[PAYLOAD_HEADER 24 bytes, message_type=0]
  message_type:     u8  = 0
  <padding>:        7 bytes
  frame_number:     i64 LE
  number_of_cameras: i32 LE
  <padding>:        4 bytes

[FRAME_HEADER 56 bytes, message_type=1] + [JPEG bytes]
  message_type:         u8  = 1
  <padding>:            7 bytes
  frame_number:         i64 LE
  camera_identifier:    [u8; 16]  (UTF-8, null-padded)
  camera_index:         i32 LE
  image_width:          i32 LE   (after rotation)
  image_height:         i32 LE   (after rotation)
  color_channels:       i32 LE   (3)
  jpeg_string_length:   i32 LE   (length of following JPEG)
  <padding>:            4 bytes

  ... repeat per camera ...

[PAYLOAD_FOOTER 24 bytes, message_type=2]
  Same structure as header
```

## Rust Implementation

```rust
#[repr(C)]
pub struct PayloadHeader {       // 24 bytes — compile-time verified
    pub message_type: u8,
    _padding1: [u8; 7],
    pub frame_number: i64,
    pub number_of_cameras: i32,
    _padding2: [u8; 4],
}

#[repr(C)]
pub struct FrameHeader {         // 56 bytes — compile-time verified
    pub message_type: u8,
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

Sizes verified at compile time: `const _: () = assert!(size_of::<PayloadHeader>() == 24);`

### Image Processing: MJPEG Passthrough

The planned pipeline (decode BGR → rotate → resize 50% → JPEG Q80) is NOT used for MJPEG. Instead:
- **MJPEG frames pass through as raw bytes** — the camera's hardware-encoded JPEG
- **Lossless rotation** via turbojpeg `tjTransform` in the dispatcher
- **Native resolution** sent to frontend (no 50% resize)
- **No `displayImageSizes` from frontend** — display size preferences not forwarded

The RGB fallback path (`resize_rgb` → `jpeg_encode_rgb` at quality 80, `FilterType::Triangle` ≈ INTER_LINEAR) exists only for non-MJPEG cameras.

### Multiframe Timestamp

Uses mean of `frame_available_ns` across cameras (not grab midpoint — no grab/retrieve split in `openpnp-capture`). Included as `timestamp_ns` in the `FrontendPayload` struct alongside the binary bytes.

### WebSocket Handler

Single async loop polling every 10ms:
- Reads `latest_frontend_payload()` from the active camera group
- Sends binary frame if `frame_number > last_frame_number`
- Sends framerate JSON at ~4 Hz (via `FramerateTracker`)
- Drains log relay messages (non-blocking)

No `frameNumber` backpressure from frontend — TCP backpressure is the only flow control.

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Byte layout | numpy dtype with `align=True` | `#[repr(C)]` struct, compile-time size assert |
| Serialization | Manual bytearray assembly | `bytemuck::bytes_of()` or raw pointer copy |
| JPEG source | `cv2.imencode('.jpg')` at quality 80 | Camera's native MJPEG (hardware encode) |
| Image resize | 50% via `cv2.resize(INTER_LINEAR)` | None — native resolution (MJPEG passthrough) |
| Rotation | `cv2.rotate()` on BGR | turbojpeg `tjTransform` (DCT-domain, lossless) |
| Timestamp | `mean(pre_grab, post_grab)` midpoint | `frame_available_ns` (single timestamp) |
| WebSocket tasks | 4 concurrent async tasks | 1 async loop with 10ms poll |
| Flow control | Cooperative `frameNumber` acks | TCP backpressure only |
