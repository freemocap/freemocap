# Pipeline Architecture

## Directory Layout

```
pipeline/
├── __init__.py
├── PIPELINE_ARCHITECTURE.md
│
├── shared/                           # Cross-cutting infrastructure
│   ├── __init__.py
│   ├── base_node.py                  # BaseNode (lifecycle: start/shutdown/is_alive)
│   ├── pipeline_ipc.py               # PipelineIPC (shared flags, pubsub, heartbeat)
│   ├── pipeline_configs.py           # DetectorSpec, task configs, RealtimePipelineConfig
│   ├── calibration_state.py          # CalibrationStateTracker (validity + graceful degradation)
│   └── frontend_payload.py           # FrontendPayload (websocket serialization)
│
├── realtime/                         # Long-lived camera-bound pipelines
│   ├── __init__.py
│   ├── realtime_camera_node.py       # RealtimeCameraNode (reads SHM, runs detectors)
│   ├── realtime_aggregation_node.py  # RealtimeAggregationNode (with CalibrationStateTracker)
│   ├── realtime_pipeline.py          # RealtimePipeline + RealtimePipelineState
│   └── realtime_pipeline_manager.py  # RealtimePipelineManager (singleton per camera set)
│
├── posthoc/                          # Fire-and-forget video processing pipelines
│   ├── __init__.py
│   ├── video_node.py                 # VideoNode (generic, parameterized by DetectorSpec)
│   ├── video_group_helper.py         # VideoHelper / VideoGroupHelper (with frame caching)
│   ├── posthoc_aggregation_node.py   # PosthocAggregationNode (generic, parameterized by task_fn)
│   ├── posthoc_pipeline.py           # PosthocPipeline (generic fire-and-forget)
│   ├── posthoc_pipeline_manager.py   # PosthocPipelineManager (lazy dead-pipeline eviction)
│   └── posthoc_tasks/
│       ├── __init__.py
│       ├── calibration_task/         # run_calibration_task() — anipose + charuco model
│       └── mocap_task/               # run_mocap_task() — mediapipe triangulation
```

## External Dependencies (from skellycam)

The pipeline uses two key classes from `skellycam.core.ipc.process_management`:

- **`ManagedProcess`**: A `multiprocessing.Process` subclass that installs SIGTERM/SIGINT handlers, auto-configures child logging (including websocket log forwarding), fires an atexit safety net on unclean exit, and provides escalating parent-side shutdown (wait → SIGTERM → SIGKILL, always joins to prevent zombies).

- **`ProcessRegistry`**: Tracks all `ManagedProcess` instances, owns the parent heartbeat timestamp (so children can detect parent death), runs a child-monitor thread (triggers parent shutdown on unexpected child death), and provides `shutdown_all()` with escalating force across all registered processes.


## Key Design Decisions

### 1. BaseNode eliminates lifecycle boilerplate

Every node (realtime camera, realtime aggregation, video, posthoc aggregation) inherits from `BaseNode` which provides:

- **`shutdown_self_flag`** + **`worker`** fields (the per-node shutdown signal and its `ManagedProcess`)
- **`start()`** — starts the child process (raises if already running)
- **`shutdown()`** — sets `shutdown_self_flag`, then delegates to `ManagedProcess.terminate_gracefully()` for escalating shutdown (wait → SIGTERM → SIGKILL)
- **`is_alive`** property
- **`_create_worker()`** static helper — creates the `shutdown_self_flag` + `ManagedProcess` pair, auto-injects the flag into the child's kwargs

Subclasses define two things: a `@classmethod create()` factory and a `@staticmethod _run()` method. The `_run()` method is the child-side entry point and always receives `shutdown_self_flag` + `ipc` as kwargs. The main loop pattern is:

```python
while not shutdown_self_flag.value and ipc.should_continue:
    # do work
```

### 2. VideoNode is parameterized by DetectorSpec

Instead of `CalibrationVideoNode` and `MocapVideoNode` (which were identical except for detector creation), there's one `VideoNode` that receives a `DetectorSpec` (which is `CharucoDetectorConfig | MediapipeDetectorConfig`). The video node calls `create_detector_from_spec()` inside the child process.

### 3. PosthocAggregationNode is parameterized by a task function

The frame-collection loop (which was duplicated line-for-line) is written once. After collecting all frames, it calls a `task_fn` that does the actual processing.

Task functions are plain module-level functions with task-specific config pre-bound via `functools.partial`:

```python
task_fn = functools.partial(run_calibration_task, task_config=calib_config)
pipeline = PosthocPipeline.create(..., aggregation_task_fn=task_fn, ...)
```

### 4. Adding a new posthoc task

To add a new task (e.g., posthoc RTMPose processing):

1. Write `posthoc_tasks/rtmpose_task.py` with a `run_rtmpose_task()` function
2. Add a factory method to `PosthocPipelineManager`:
   ```python
   def create_rtmpose_pipeline(self, ...) -> PosthocPipeline:
       task_fn = functools.partial(run_rtmpose_task, task_config=rtmpose_config)
       return PosthocPipeline.create(
           ..., detector_spec=rtmpose_config.detector_spec, aggregation_task_fn=task_fn, ...
       )
   ```

No new Node classes. No new Pipeline classes.

### 5. CalibrationStateTracker

The realtime aggregation node uses `CalibrationStateTracker` which:
- **Optimistically loads** the latest calibration on startup
- **Gracefully degrades** on triangulation failure (invalidates and publishes 2D-only data)
- **Reloads on config update** (so after a posthoc calibration completes, the frontend sends a config update and the realtime pipeline picks up the new calibration)

### 6. Progress reporting

Posthoc pipelines publish `PosthocProgressMessage` with:
- `phase`: "collecting_frames" | "processing" | "complete" | "failed"
- `progress_fraction`: 0.0 to 1.0
- `detail`: human-readable string

Subscribe to `PosthocProgressTopic` to monitor posthoc pipeline status.

### 7. Pipeline managers

There are two manager classes with different lifecycle semantics:

- **`RealtimePipelineManager`**: Manages long-lived pipelines, one per camera ID set. Creating a pipeline for an already-tracked set returns the existing one with an updated config. Provides frontend payload streaming across all pipelines.

- **`PosthocPipelineManager`**: Manages fire-and-forget pipelines. Pipelines self-terminate on completion. Dead entries are evicted lazily on access. Provides factory methods for each task type (`create_calibration_pipeline`, `create_mocap_pipeline`).

### 8. Error handling

- **Posthoc nodes**: on exception → `ipc.shutdown_pipeline()` (pipeline-local, doesn't kill the app)
- **Realtime nodes**: on exception → `ipc.kill_everything()` (realtime failure = app-level problem)
- **ManagedProcess**: unhandled exceptions in child → sets `global_kill_flag` + re-raises
- **ProcessRegistry child monitor**: unexpected child death → sets `global_kill_flag` + sends SIGTERM to parent

### 9. Shutdown flow

Shutdown is layered and escalating:

1. **Cooperative**: `PipelineIPC.should_continue` returns `False` (checks `global_kill_flag`, `pipeline_shutdown_flag`, and parent heartbeat). Nodes exit their main loops naturally.
2. **Per-node**: `BaseNode.shutdown()` sets `shutdown_self_flag` then calls `ManagedProcess.terminate_gracefully()` (wait → SIGTERM → SIGKILL).
3. **Registry-wide**: `ProcessRegistry.shutdown_all()` sets `global_kill_flag`, waits, then SIGTERM stragglers, then SIGKILL. Always joins all processes to prevent zombies.
4. **Safety net**: `ProcessRegistry._atexit_cleanup()` catches anything that slipped through.


## Process Hierarchy

```
Main Process (FastAPI / app server)
├── ProcessRegistry
│   ├── heartbeat thread (writes timestamp every 1s)
│   └── child monitor thread (detects unexpected child death)
│
├── RealtimePipeline (per camera group)
│   ├── RealtimeCameraNode (per camera) ← ManagedProcess
│   └── RealtimeAggregationNode         ← ManagedProcess
│
└── PosthocPipeline (fire-and-forget, 0..N concurrent)
    ├── VideoNode (per video file)       ← ManagedProcess
    └── PosthocAggregationNode           ← ManagedProcess
```

All child processes are `ManagedProcess` instances, registered in the `ProcessRegistry`. They share:
- `global_kill_flag` (app-wide shutdown)
- `heartbeat_timestamp` (parent liveness detection)
- Per-pipeline `PipelineIPC` (pipeline-scoped shutdown + pubsub)

