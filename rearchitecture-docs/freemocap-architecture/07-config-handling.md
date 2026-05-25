# Config Handling & Hot-Swappable Backend

> Step 2 (Extract Invariants) + Step 4 (Design Rust) — real-time config updates and Python/Rust backend switching.

## The Problem

The pipeline must be real-time configurable from the UI. Changing charuco board parameters, toggling triangulation on/off, adjusting filter parameters — all must apply without restarting the pipeline. Additionally, the system must support switching between the Rust and Python pipeline implementations at runtime.

### Invariants

- Config updates apply to all running nodes within one frame cycle
- Charuco detector is recreated when board parameters change
- Filter parameters update in-place (no recreation needed)
- Toggling triangulation on/off takes effect immediately
- Single boolean flag selects Rust vs Python backend
- Manager-level decision (matching skellycam's pattern)
- Config serialized as JSON is the interchange format between Python and Rust

## Config Flow

```
┌─ Python (FastAPI route) ─────────────────────────────────┐
│  POST /pipeline/config/update                            │
│    Body: { "charuco_config": {...}, "filter_config": ... }│
│    → Pydantic RealtimePipelineConfig validation           │
│    → pipeline_manager.update_pipeline_config(...)         │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌─ RealtimePipelineManager ────────────────────────────────┐
│  def update_pipeline_config(self, pipeline_id, config):   │
│    pipeline = self.pipelines[pipeline_id]                 │
│    pipeline.update_config(config)                         │
│      │                                                     │
│      │  if Rust: self._inner.update_config(json)           │
│      │  if Python: self.pubsub.publish(config_msg)         │
└──────────────────────┬───────────────────────────────────┘
                       │ (Rust path)
                       ▼
┌─ PyO3 bridge ────────────────────────────────────────────┐
│  PyPipeline.update_config(config_json: str)               │
│    let config: PipelineConfig = serde_json::from_str()?;  │
│    for sender in &self.cmd_senders {                      │
│      sender.send(PipelineCommand::UpdateConfig(config))?; │
│    }                                                      │
└──────────────────────┬───────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    Distributor   CameraNode[0]   Aggregator
    cmd_rx        cmd_rx          cmd_rx
    .try_recv()   .try_recv()     .try_recv()
```

## Config Struct

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PipelineConfig {
    pub charuco_config: CharucoDetectorConfig,
    pub triangulation_enabled: bool,
    pub filter_config: FilterConfig,
    pub skeleton_enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CharucoDetectorConfig {
    pub squares_x: u32,
    pub squares_y: u32,
    pub square_length_mm: f64,
    pub marker_length_mm: f64,
    pub dictionary_id: u32,
    pub refine_corners: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FilterConfig {
    pub filter_enabled: bool,
    pub min_cutoff: f64,
    pub beta: f64,
    pub d_cutoff: f64,
    pub max_velocity_m_per_s: f64,
    pub max_reprojection_error_px: f64,
    pub max_rejected_streak: u32,
    pub skeleton_enabled: bool,
}
```

Python's Pydantic `RealtimePipelineConfig` serializes to the same JSON shape. No dual-maintenance — the JSON is the contract.

## Node-Specific Config Application

### Camera Nodes

```rust
fn apply_config(&mut self, config: &PipelineConfig) {
    // Charuco detector must be recreated when board params change
    if self.current_charuco_config != config.charuco_config {
        self.detector = CharucoTracker::from_config(&config.charuco_config);
        self.current_charuco_config = config.charuco_config.clone();
    }
}
```

### Aggregator

```rust
fn apply_config(&mut self, config: &PipelineConfig) {
    self.config = config.clone();

    // Filter params update in-place (no recreation needed)
    self.keypoint_filter.set_params(
        config.filter_config.min_cutoff,
        config.filter_config.beta,
        config.filter_config.d_cutoff,
    );
    self.velocity_gate.set_max_velocity(config.filter_config.max_velocity_m_per_s);
}
```

### Distributor

```rust
fn apply_config(&mut self, config: &PipelineConfig) {
    // Camera count may have changed
    if config.camera_ids.len() != self.barrier.total() - 1 {
        self.barrier.set_total(config.camera_ids.len() + 1);
    }
}
```

## Hot-Swappable Backend (Manager-Level)

Following skellycam's `CameraGroupManager` pattern exactly:

```python
# freemocap/core/pipeline/realtime/realtime_pipeline_manager.py

USE_RUST_BACKEND: bool = True  # module-level flag

class RealtimePipelineManager(PipelineManagerABC):
    pipelines: dict[PipelineIdString, RealtimePipeline | RustRealtimePipeline]

    def create_pipeline(self, *, camera_group, pipeline_config, realtime_camera_ids=None):
        with self.lock:
            # Check for existing pipeline (same logic either backend)
            for pipeline in self.pipelines.values():
                if set(pipeline.camera_ids) == set(pipeline_config.camera_ids):
                    pipeline.update_config(new_config=pipeline_config)
                    return pipeline

            # Single decision point — HERE, not in a factory function
            if USE_RUST_BACKEND:
                pipeline = RustRealtimePipeline(
                    camera_group=camera_group,
                    pipeline_config=pipeline_config,
                    realtime_camera_ids=realtime_camera_ids,
                )
            else:
                pipeline = RealtimePipeline.create(
                    camera_group=camera_group,
                    worker_registry=self.worker_registry,
                    pipeline_config=pipeline_config,
                    realtime_camera_ids=realtime_camera_ids,
                )

            pipeline.start()
            self.pipelines[pipeline.id] = pipeline
            return pipeline
```

### The Adapter

```python
class RustRealtimePipeline:
    """Wraps _freemocap_rust.Pipeline. Thin — no backend flag, no factory."""

    def __init__(self, *, camera_group, pipeline_config, realtime_camera_ids=None):
        self.id = str(uuid.uuid4())[:6]
        self.camera_group = camera_group
        native = _get_native()
        self._inner = native.Pipeline(
            camera_group._native_manager,
            pipeline_config.model_dump_json(),
            realtime_camera_ids or list(camera_group.configs.keys()),
        )

    @property
    def camera_ids(self) -> list[str]:
        return self._inner.camera_ids()

    @property
    def camera_group_id(self) -> str:
        return self.camera_group.id

    @property
    def alive(self) -> bool:
        return self._inner.alive()

    def start(self) -> None:
        self._inner.start()

    def shutdown(self) -> None:
        self._inner.shutdown()

    def update_config(self, new_config: RealtimePipelineConfig) -> None:
        self._inner.update_config(new_config.model_dump_json())

    def get_latest_frontend_payload(self, if_newer_than: int):
        return self._inner.get_latest_output(if_newer_than)
```

### Why Manager-Level (Not Factory-Level)

In skellycam, `USE_RUST_BACKEND` lives in `camera_group_manager.py` — the manager decides which backend to instantiate. Individual `CameraGroup` objects don't know or care whether they're Rust or Python. The manager is the single decision point.

Skellytracker's `get_brightest_point_tracker()` factory function pattern was a compromise: beartype forced `BaseTracker` subclassing at every call boundary, so the factory was the natural gate. For the pipeline, the manager is already the gate — adding a factory function would just add indirection.

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Config propagation | PubSub broadcast to all subscribers | Direct `mpsc::Sender` to each node |
| Config validation | Pydantic `BaseModel` | `#[derive(Deserialize)]` + serde |
| Charuco param change | Recreate `CharucoDetector` | Recreate `CharucoTracker` |
| Filter param change | In-place attribute update | In-place setter methods |
| Backend switch | N/A (only Python backend) | `USE_RUST_BACKEND` in manager |
| Adapter pattern | N/A | `RustRealtimePipeline` thin wrapper |
