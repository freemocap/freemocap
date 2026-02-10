# Pipeline Architecture 

## Directory Layout

```
pipeline/
├── __init__.py
├── configs.py                  # All config types + DetectorSpec
├── ipc.py                      # PipelineIPC (shared flags, pubsub, heartbeat)
├── calibration_state.py        # CalibrationStateTracker (validity + graceful degradation)
├── frontend_payload.py         # FrontendPayload (unchanged)
│
├── nodes/
│   ├── __init__.py             # BaseNode (lifecycle boilerplate)
│   ├── video_node.py           # VideoNode (generic, parameterized by DetectorSpec)
│   ├── posthoc_aggregation_node.py   # PosthocAggregationNode (generic, parameterized by task_fn)
│   ├── realtime_camera_node.py       # RealtimeCameraNode (reads SHM, runs detectors)
│   └── realtime_aggregation_node.py  # RealtimeAggregationNode (with CalibrationStateTracker)
│
├── realtime_pipeline.py        # RealtimePipeline (long-lived, config-updatable)
├── posthoc_pipeline.py         # PosthocPipeline (generic fire-and-forget)
├── pipeline_manager.py         # PipelineManager (unified, with auto-cleanup reaper)
│
├── posthoc_tasks/
│   ├── __init__.py
│   ├── calibration_task.py     # run_calibration_task() — anipose + charuco model
│   └── mocap_task.py           # run_mocap_task() — mediapipe triangulation
│
├── posthoc_pipelines/
│   ├── video_helper.py         # VideoHelper / VideoGroupHelper (unchanged)
│   └── posthoc_calibration_pipeline/
│       └── calibration_helpers/  # Heavy math (unchanged)
│
└── (pubsub_topics.py lives in freemocap/pubsub/ — updated version included)
```

## Key Design Decisions

### 1. BaseNode eliminates lifecycle boilerplate

Every node (realtime camera, realtime aggregation, video, posthoc aggregation)
inherits from `BaseNode` which provides `start()`, `shutdown()`, and `is_alive`.
No more copy-pasted shutdown logic with inconsistent terminate/terminate_gracefully calls.

### 2. VideoNode is parameterized by DetectorSpec

Instead of `CalibrationVideoNode` and `MocapVideoNode` (which were identical except
for detector creation), there's one `VideoNode` that receives a `DetectorSpec`
(which is just `CharucoDetectorConfig | MediapipeDetectorConfig`). The video node
calls `create_detector_from_spec()` inside the child process.

### 3. PosthocAggregationNode is parameterized by a task function

The frame-collection loop (which was duplicated line-for-line) is written once.
After collecting all frames, it calls a `task_fn` that does the actual processing.

Task functions are plain module-level functions with task-specific config pre-bound
via `functools.partial`:

```python
task_fn = functools.partial(run_calibration_task, task_config=calib_config)
pipeline = PosthocPipeline.create(..., task_fn=task_fn, ...)
```

### 4. Adding a new posthoc task

To add a new task (e.g., posthoc RTMPose processing):

1. Write `posthoc_tasks/rtmpose_task.py` with a `run_rtmpose_task()` function
2. Add a factory method to `PipelineManager`:
   ```python
   def create_posthoc_rtmpose_pipeline(self, ...) -> PosthocPipeline:
       task_fn = functools.partial(run_rtmpose_task, task_config=rtmpose_config)
       return PosthocPipeline.create(..., detector_spec=rtmpose_config.detector_spec, task_fn=task_fn, ...)
   ```

No new Node classes. No new Pipeline classes.

### 5. CalibrationStateTracker

The realtime aggregation node uses `CalibrationStateTracker` which:
- **Optimistically loads** the latest calibration on startup
- **Gracefully degrades** on triangulation failure (invalidates and publishes 2D-only data)
- **Reloads on config update** (so after a posthoc calibration completes, the frontend
  sends a config update and the realtime pipeline picks up the new calibration)

### 6. Progress reporting

Posthoc pipelines publish `PosthocProgressMessage` with:
- `phase`: "collecting_frames" | "processing" | "complete" | "failed"
- `progress_fraction`: 0.0 to 1.0
- `detail`: human-readable string

Subscribe to `PosthocProgressTopic` to monitor posthoc pipeline status.

### 7. Auto-cleanup reaper

`PipelineManager` runs a background thread that checks every ~10s for dead posthoc
pipelines. If a pipeline self-completed cleanly, it logs info and removes it. If it
died with non-zero exit codes, it logs warnings.

### 8. Error handling

- **Posthoc nodes**: on exception, call `ipc.shutdown_pipeline()` (pipeline-local, doesn't kill the app)
- **Realtime nodes**: on exception, call `ipc.kill_everything()` (realtime failure = app-level problem)

## Migration Notes

### Renamed types
- `CalibrationpipelineConfig` → `CalibrationPipelineConfig`
- `MocapPipelineTaskConfig` → `MocapPipelineConfig`
- `RealtimeProcessingPipeline` → `RealtimePipeline`
- `PosthocCalibrationProcessingPipeline` / `PosthocMocapProcessingPipeline` → `PosthocPipeline`
- `RealtimePipelineManager` + `PosthocPipelineManager` → `PipelineManager`

### Removed
- `CalibrationVideoNode` — use `VideoNode` with charuco `DetectorSpec`
- `MocapVideoNode` — use `VideoNode` with mediapipe `DetectorSpec`
- `PosthocCalibrationAggregationNode` — use `PosthocAggregationNode` with `run_calibration_task`
- `PosthocMocapAggregationNode` — use `PosthocAggregationNode` with `run_mocap_task`
- `RealtimePipeline.start_calibration_recording()` — orchestration belongs in route handlers
- `RealtimePipeline.stop_calibration_recording()` — same

### Config field renames
- `calibration_task_config` → `calibration_config`
- `mocap_task_config` → `mocap_config`
- New: `calibration_detection_enabled: bool` and `mocap_detection_enabled: bool` toggles
