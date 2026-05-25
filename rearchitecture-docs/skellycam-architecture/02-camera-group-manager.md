# Camera Group Manager

> Worked example of Step 1 (Understand) + Step 2 (Extract Invariants) + Step 3 (Separate Python Concerns) from the [re-architecture playbook](../rearchitecture-playbook/).

## The Problem

Manage the lifecycle of synchronized camera groups. Create groups from configs, start/stop recording, pause/unpause, update settings on running cameras, and cleanly shut down.

### Invariants

- Camera group is the top-level managed entity — API creates/reads/updates/destroys groups
- Config updates must propagate to running cameras without restart
- Multiple camera groups can coexist independently
- Clean shutdown of individual groups without affecting others
- HTTP endpoints with same paths and JSON shapes (frontend compatibility)

## Python's Solution

Three-layer hierarchy:

```
CameraGroupManager  ← singleton, owns all groups
    └── CameraGroup  ← owns IPC, SharedMemory, CameraManager
        └── CameraManager  ← creates CameraWorkers + CameraOrchestrator
```

**Two-phase startup**: spawn camera processes → wait for each to publish `DeviceExtractedConfigMessage` via PubSub → allocate shared memory sized for actual resolutions → publish SHM DTOs to children → start capture.

**Recording**: pause all cameras → set `first_recording_frame_number = current + 3` → publish `RecordingInfoMessage` → unpause. The +3 offset ensures all cameras see the recording boundary.

**Shared memory**: `SharedMemory` ring buffers created in main process, DTOs (name + dtype) passed via PubSub, children `recreate()` from DTOs.

### Python-Specific Decisions

| Mechanism | Why Python Needs It |
|-----------|-------------------|
| Module-level global singleton | FastAPI has no built-in DI; route handlers are stateless |
| Two-phase startup with extracted configs | Config extracted in child process must cross process boundary |
| Shared memory created after config known | SHM size depends on actual frame dimensions |
| DTO/recreate pattern | Each process must independently map shared memory by name |
| Pause-before-record protocol with +3 offset | Recording boundaries must be communicated via shared `Value("q")` |
| `await_extracted_configs()` polling loop | Async PubSub wait — each camera publishes, main polls |

## Rust's Solution

### CameraGroupManager

```rust
pub struct CameraGroupManager {
    groups: HashMap<String, CameraGroup>,
}
```

Wrapped in `Mutex<CameraGroupManager>` inside `Arc<AppState>` — no module-level global. The singleton emerges from having one `AppState` passed to the Axum router.

### CameraGroup

**Startup** (single phase — no extracted configs dance):
1. Pause all cameras (`paused = true`)
2. Create `BreakableBarrier` with count = camera_count + 1
3. Spawn each camera via `Camera::start()` — failed spawns logged and skipped
4. Wait for each camera to send `Ready` via `wait_until_ready(timeout)`
5. Correct barrier count for actual cameras
6. Take frame receivers via `take_frame_receiver()`
7. Spawn gatherer + dispatcher threads
8. Unpause → `Streaming`

**No SHM, no DTOs, no two-phase startup.** Cameras self-configure during `Camera::start()` — `find_best_mjpg()` negotiates format, writes actual resolution/framerate to `Arc<Mutex<CameraConfig>>`. All threads see the same config through the `Arc`.

**Recording**: `start_recording(params)` sends `DispatcherCommand::StartRecording`. `stop_recording()` sends `StopRecording`, receives `RecordingSummary` via oneshot. No pause-before-record, no +3 offset.

**Config updates**: `Camera::configure(config)` sends `CameraCommand::Configure` to the camera thread. `apply_config()` handles exposure-only changes in-place; resolution/framerate changes restart the stream.

### CameraStatus (radically simplified)

Python's 11 `multiprocessing.Value` booleans collapse to:
- `paused: Arc<AtomicBool>` — shared across all cameras in a group
- Camera events via `mpsc::channel` (`Ready`, `Error`)
- No individual `is_paused`, `should_close`, `connected`, `error`, `closing`, `closed`, `updating` flags

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Singleton | Module-level global | `Arc<AppState>` with `Mutex<CameraGroupManager>` |
| Startup | Two-phase: spawn → wait for extracted configs → create SHM → notify | Single-phase: cameras self-configure, results in shared `Arc<Mutex<Config>>` |
| Frame buffering | `SharedMemory` ring buffers with DTO/recreate | Heap `Vec<u8>` shared via `Arc` or channels |
| Camera status | 11 per-camera `multiprocessing.Value` booleans | 1 `Arc<AtomicBool>` for paused + event channel |
| Recording start | Pause → set boundaries → publish → unpause | Direct dispatcher command, on-the-fly |
| Config propagation | PubSub broadcast + polling | Direct `mpsc::Sender<CameraCommand::Configure>` |
