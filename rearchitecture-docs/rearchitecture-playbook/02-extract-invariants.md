# Step 2: Extract the Invariants

Before designing anything in Rust, identify what CANNOT change. These are the constraints that any reimplementation must satisfy, regardless of language.

The frontend and downstream consumers depend on these. If you break them, nothing works.

## Categories of Invariants

### API Contracts

- **Endpoint paths**: exact URL paths the frontend calls (e.g., `POST /skellycam/camera/detect`)
- **HTTP methods**: GET, POST, DELETE — match them exactly, even if they seem wrong (e.g., `POST` for a read-only detection endpoint)
- **Request body shapes**: JSON field names, types, nesting structure
- **Response body shapes**: JSON field names, types, nesting structure
- **Error format**: the frontend parses error responses — match the structure exactly (e.g., `{"detail": "<message>"}` with status 500)
- **Status codes**: match the Python implementation

### Binary Protocols

- **Byte layouts**: exact struct sizes, field offsets, endianness
- **Message framing**: how the receiver knows where one message ends and the next begins
- **Magic numbers / type tags**: byte values that identify message types
- **Encoding**: JPEG quality, pixel format (RGB vs BGR), color channel order

### File Formats

- **Directory structure**: recording folder layout the frontend expects
- **File naming conventions**: how video files, timestamp CSVs, and metadata JSON are named
- **CSV column names and order**: if downstream tools parse these, they must match
- **Metadata JSON fields**: the frontend reads recording metadata — don't rename fields

### Behavioral Requirements

- **Multi-camera lockstep**: all cameras must produce frames at the same frame number
- **Recording boundaries**: recording start/stop must be consistent across cameras
- **Graceful shutdown**: Ctrl+C or API shutdown must cleanly release all resources
- **Pause/resume**: pausing must stop frame capture without dropping the camera connection
- **Config updates mid-stream**: changing camera settings must work without stopping capture

## How to Find Them

1. **Read the frontend code** — what API calls does it make? What JSON fields does it read?
2. **Read the WebSocket handling code** — what binary messages does it parse? What JSON messages does it send/receive?
3. **Trace a recording from start to finish** — what files are created? Where? What's in them?
4. **Look for validation code** — assertions, type checks, field existence checks. These encode invariants.
5. **Look for hardcoded values** — magic numbers, fixed-size buffers, string constants in the frontend. These are de facto invariants even if undocumented.

## Output

A checklist of invariants organized by category. Each item should be specific enough that you can verify it:

```
- [ ] POST /skellycam/camera/detect returns {"cameras": [...]} with camera_id, camera_index, resolution fields
- [ ] Binary payload header is exactly 24 bytes with message_type at offset 0
- [ ] Recording folder is {dir}/{name}/synchronized_videos/{name}.camera{id}.mp4
- [ ] All cameras must be at the same frame number before a multiframe is emitted
```

## Concrete Examples from SkellyCam

| Invariant | Why It Matters |
|-----------|---------------|
| `PayloadHeader` is exactly 24 bytes, `FrameHeader` 56 bytes, `#[repr(C)]` layout | The frontend JavaScript parses these exact byte offsets |
| message_type values: 0 = header, 1 = frame, 2 = footer | The frontend uses these to navigate a stream of concatenated binary messages |
| `POST /skellycam/camera/detect` — POST, not GET | The frontend hardcodes POST for camera detection |
| Error responses: `{"detail": "<message>"}` with status 500 | The frontend error display reads `error.detail` |
| Recording videos: `synchronized_videos/Camera_{index}_{id}_{label}.mp4` | The playback UI reconstructs paths from these components |
