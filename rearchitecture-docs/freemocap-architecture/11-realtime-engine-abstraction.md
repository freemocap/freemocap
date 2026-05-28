# RealtimeEngine — Unified Camera + Pipeline Abstraction

> Bundles camera management and real-time pipeline management behind a single interface. Swap between Python and Rust implementations with a module-level constant.

## The Problem

Currently `FreemocapApplication` holds two separate managers:

- `camera_group_manager: CameraGroupManager` — camera lifecycle, recording, pause
- `realtime_pipeline_manager: RealtimePipelineManager` — pipeline lifecycle, frame output, backpressure

On the Rust side, there are two separate PyO3 objects:

- `_skellycam_rust.CameraGroupManager` (`PyO3CameraGroupManager`) — camera capture
- `_freemocap_rust.PyPipeline` — pipeline engine (extracts FrameSlots from the camera manager internally)

To swap between Python and Rust, you'd need to swap two objects in two different places, ensuring they're compatible. The Rust pipeline **must** use the Rust camera group (it extracts `FrameSlots` via Rust-to-Rust casting). The Python pipeline **must** use the Python `CameraGroup` (multiprocessing IPC). Cross-pairing doesn't work.

## Solution

**One "RealtimeEngine" abstraction** that bundles both concerns. A single object handles camera creation, pipeline lifecycle, frame output, recording, and shutdown. `FreemocapApplication` holds one `realtime_engine` instead of two separate managers.

### Architecture

```
┌─ FreemocapApplication ───────────────────────────────────┐
│  realtime_engine: RealtimeEngine   (one object, not two)  │
│  posthoc_pipeline_manager: PosthocPipelineManager         │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Python path:                          Rust path:         │
│  ┌─ PythonRealtimeEngine ──┐          ┌─ RustRealtimeEngine ──┐
│  │                          │          │                        │
│  │ CameraGroupManager       │          │ _freemocap_rust       │
│  │   (multiprocessing)      │          │   .RealtimeEngine     │
│  │                          │          │   (one PyO3 class)    │
│  │ RealtimePipelineManager  │          │                        │
│  │   (multiprocessing)      │          │ Internally manages:    │
│  │                          │          │ - PyO3CameraGroupMgr  │
│  └──────────────────────────┘          │ - Pipeline threads    │
│                                        └────────────────────────┘
│                                                           │
│  Both expose the same 9 methods:                           │
│  create_or_update_camera_group, create_pipeline,           │
│  get_latest_frontend_payloads, wait_for_any_result_ready,  │
│  start_recording_all, stop_recording_all,                  │
│  pause_unpause_all, shutdown, pipelines (property)          │
└───────────────────────────────────────────────────────────┘
```

### Swap mechanism

```python
# freemocap/app/freemocap_application.py

USE_RUST_BACKEND: bool = False  # ← module-level constant, flip to True for Rust

@dataclass
class FreemocapApplication:
    realtime_engine: RealtimeEngine  # ← single object, not two managers
    posthoc_pipeline_manager: PosthocPipelineManager  # ← unchanged

    @classmethod
    def create(cls, ...):
        if USE_RUST_BACKEND:
            engine = RustRealtimeEngine()
        else:
            engine = PythonRealtimeEngine(
                worker_registry=worker_registry,
                global_kill_flag=global_kill_flag,
            )
        return cls(realtime_engine=engine, ...)
```

## Interface

Traced from actual call sites in `freemocap_application.py` and `websocket_server.py`. Both `PythonRealtimeEngine` and `RustRealtimeEngine` implement these methods:

| Method | Source (which manager currently handles it) |
|--------|------|
| `create_or_update_camera_group(camera_configs) → CameraGroup` | `camera_group_manager` |
| `create_pipeline(*, camera_group, pipeline_config, camera_ids) → pipeline` | `realtime_pipeline_manager` |
| `pipelines → dict[str, pipeline]` (property) | `realtime_pipeline_manager` |
| `wait_for_any_result_ready(timeout) → None` (async) | `realtime_pipeline_manager` |
| `get_latest_frontend_payloads(if_newer_than) → list[FrontendImagePacket]` | Both (normalized by engine) |
| `start_recording_all(recording_info) → None` (async) | `camera_group_manager` |
| `stop_recording_all() → list[tuple[RecordingInfo, RecordingTimestampsStats]]` (async) | `camera_group_manager` |
| `pause_unpause_all() → None` | `realtime_pipeline_manager` |
| `shutdown() → None` | Both |

## PythonRealtimeEngine

Thin wrapper that delegates to the existing `CameraGroupManager` + `RealtimePipelineManager`. No logic changes — the existing code keeps running exactly as before. The engine is just a unified facade.

```python
class PythonRealtimeEngine:
    def __init__(self, worker_registry, global_kill_flag):
        self._camera_mgr = CameraGroupManager(...)
        self._pipeline_mgr = RealtimePipelineManager(worker_registry=worker_registry)

    async def create_or_update_camera_group(self, camera_configs):
        return await self._camera_mgr.create_or_update_camera_group(camera_configs)

    def create_pipeline(self, *, camera_group, pipeline_config, realtime_camera_ids=None):
        return self._pipeline_mgr.create_pipeline(
            camera_group=camera_group,
            pipeline_config=pipeline_config,
            realtime_camera_ids=realtime_camera_ids,
        )

    @property
    def pipelines(self):
        return self._pipeline_mgr.pipelines

    # ... etc for all 9 methods
```

## PyRealtimeEngine (Rust)

A single `#[pyclass]` registered in `_freemocap_rust` that bundles everything. Python sees one object — no separate camera manager + pipeline objects to orchestrate.

```rust
#[pyclass(name = "RealtimeEngine")]
pub struct PyRealtimeEngine {
    camera_manager: PyO3CameraGroupManager,    // skellycam camera handling
    pipelines: HashMap<String, PipelineState>, // pipeline threads + channels
    shutdown_flag: Arc<AtomicBool>,
}

struct PipelineState {
    camera_ids: Vec<String>,
    config: PipelineConfig,
    cmd_senders: Vec<mpsc::Sender<PipelineCommand>>,
    output_slot: Arc<Mutex<Option<AggregatorOutput>>>,
    result_ready: Arc<AtomicBool>,  // set by aggregator each frame, cleared by Python poll
    handles: Vec<JoinHandle<()>>,
}
```

Internal flow:
1. `create_or_update_camera_group(configs_dict)` → delegates to `PyO3CameraGroupManager.create_or_update_group()`, returns group_id
2. `create_pipeline(group_id, config_json, camera_ids, calibration_toml_path)` → extracts FrameSlots from camera manager, spawns distributor + N camera nodes + aggregator threads, stores pipeline state
3. `get_latest_frontend_payloads(if_newer_than)` → polls each pipeline's `output_slot`, builds `FrontendImagePacket`-equivalent PyDicts
4. `wait_for_any_result_ready(timeout_secs)` — polls `result_ready` flags with sleep backoff, returns when any pipeline has a new frame
5. `shutdown()` → sends Shutdown to all, breaks barriers, joins threads, closes camera groups

## Posthoc Boundary

`PosthocPipelineManager` is NOT part of `RealtimeEngine`. It stays as a separate object on `FreemocapApplication`:

```python
@dataclass
class FreemocapApplication:
    realtime_engine: RealtimeEngine              # NEW — cameras + realtime pipeline
    posthoc_pipeline_manager: PosthocPipelineManager  # UNCHANGED
```

Why: Posthoc pipelines are fire-and-forget, disk-based, and self-terminating. They process recorded video files, not live cameras. They share nothing with the realtime frame path. Keeping them separate avoids coupling long-running indeterminate processes (live camera loop) with single-shot batch processes (calibration, mocap processing).

## What the Rust RealtimeEngine Does NOT Handle (for now)

- **Skeleton inference** — GPU RTMPose inference stays in Python when enabled. The Rust engine handles charuco detection + triangulation only.
- **Binary keypoints protocol** — no `build_keypoints_payload()` in Rust. Keypoints are passed as Python dicts.
- **Posthoc processing** — entirely Python. Rust engine is realtime-only.
- **WebSocket relay** — stays in Python. The engine just provides frame data; the Python websocket server sends it to the frontend.

## Invariants

- `FreemocapApplication` holds one `realtime_engine`, not two managers
- `USE_RUST_BACKEND` is a module-level `bool` constant — no env vars, no runtime switching
- `PythonRealtimeEngine` delegates to the existing `CameraGroupManager` + `RealtimePipelineManager` — zero behavior changes on the Python path
- `PyRealtimeEngine` manages camera groups internally via skellycam's `PyO3CameraGroupManager` — no separate Python camera manager needed
- Posthoc pipelines are untouched by this refactor
- HTTP routes and websocket relay call `FreemocapApplication` methods — those delegate to `realtime_engine` — same signatures, no route changes
- The frontend receives identical `FrontendPayload` JSON regardless of backend

## Implementation Order

1. **Create `PythonRealtimeEngine`** — refactor only, no Rust changes. Update `FreemocapApplication` to use it. Verify nothing breaks.
2. **Build `PyRealtimeEngine`** — add the PyO3 class to `_freemocap_rust`. Add `result_ready` signaling for `wait_for_any_result_ready`.
3. **Create `RustRealtimeEngine` Python wrapper** — thin adapter around `_freemocap_rust.RealtimeEngine`.
4. **Wire `USE_RUST_BACKEND`** — flip the constant in `freemocap_application.py` to swap implementations.
5. **Smoke test** — verify camera feed + charuco overlay + triangulated keypoints appear on the frontend.