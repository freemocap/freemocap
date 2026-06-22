# E2E Test Suite for Realtime + Posthoc Mocap Pipelines

## Context

The new pipeline code under `freemocap/core/pipeline/{posthoc,realtime}/` has almost no
end-to-end coverage. The one existing E2E file (`freemocap/tests/test_e2e_pipeline.py`)
targets the new posthoc pipeline but **calibrates with the wrong charuco board** (default
5x3) for the shared test recording, and does not touch the realtime pipeline at all.

We want a real E2E suite driven by the canonical test recording at
`~/freemocap_data/recordings/freemocap_test_data` — 3 synchronized videos, 222 frames
each: a 7x5 charuco calibration sequence followed by mocap movement. The same recording
serves both calibration and mocap.

- **Posthoc**: run the real `PosthocPipelineManager` pipelines directly on the recording.
- **Realtime**: the pipeline is built around a live `CameraGroup`. We mock *only the camera
  capture* — a `MockCameraGroup` creates the **real** skellycam shared memory and feeds it
  frames read from the test videos, so the camera nodes, aggregator, triangulation, filtering
  and skeleton-fitting all run unmodified. We do **not** test camera hardware/capture.

Outcome: a runnable `freemocap/tests/pipelines/` suite proving calibration → posthoc mocap
works on real data, and that the realtime pipeline processes mocked camera frames through to
3D output. This is the foundation for later realtime-vs-posthoc validation.

## Decisions (confirmed with user)

- **Run in-place** in the canonical recording folder (matches the real app; regenerates
  `output_data/`, `annotated_videos/`, `.blend` in the source folder each run).
- **Realtime test is parametrized**: a fast charuco-only plumbing test + a heavier full
  RTMPose-skeleton + triangulation test (marked slow).
- **Realtime runs in THREAD mode** (camera nodes + aggregator as in-process threads via a
  `WorkerMode.THREAD` `WorkerRegistry`) — avoids Windows spawn/pickling and per-process model
  reloads, keeps the lockstep driver single-process and deterministic. PROCESS mode is a
  possible later variant.

## Key findings from exploration

- `RealtimePipeline.create(camera_group, worker_registry, pipeline_config, realtime_camera_ids=None)`
  reads from the camera group only: `ipc.global_kill_flag`, `configs`, `id`, `shm.to_dto()`.
  Camera nodes / aggregator `recreate()` the real shm from that DTO. (`realtime_pipeline.py`)
- The aggregator drives frames: reads `camera_group_shm.latest_multiframe_number`, publishes
  `ProcessFrameNumberMessage`; camera nodes read that frame via `get_data_by_index` and detect;
  aggregator collects, triangulates, filters, publishes `AggregationNodeOutputMessage` on
  `aggregation_output_subscription`, then `result_consumed_event.clear(); result_ready_event.set()`.
  (`realtime_aggregator_node.py`)
- Ring buffer holds ~1GB/frame-size ≈ hundreds of slots → **all 222 frames fit without
  wrapping**, so a single-threaded lockstep driver (write N → wait for output N → flip events →
  write N+1) deterministically processes every frame. (`ring_buffer_shared_memory.py`)
- Frame write recipe (mirror `run_opencv_camera_loop`): one `np.recarray(1, dtype=create_frame_dtype(config))`
  per camera with `frame_metadata.camera_info = config.to_frame_camera_info()[0]` and
  `frame_metadata.timebase_mapping`; per frame set `.image[0]`, `.frame_metadata.frame_number[0]=N`,
  timestamps, then `camera_shm.put_frame(rec, overwrite=True)`.
- **Bug A**: `RealtimePipelineManager.create_pipeline` reads `pipeline_config.camera_ids`, which
  does not exist on `RealtimePipelineConfig` → `AttributeError`. ⇒ realtime test drives
  `RealtimePipeline.create()` directly (not the manager). Flag for a follow-up fix.
- **Bug B / data**: this recording uses `CharucoBoardDefinition.create_test_data_7x5()` (7x5,
  58mm), not the config default 5x3. Calibration/charuco configs must override the board.
- Realtime aggregator loads calibration from the **global** last-successful path via
  `CalibrationStateTracker.create_and_try_load()` → `get_last_successful_calibration_toml_path()`
  (`<base>/calibrations/last_successful_camera_calibration.toml`). So the realtime 3D path needs
  calibration produced first.

## File layout (new package `freemocap/tests/pipelines/`)

```
freemocap/tests/pipelines/
  __init__.py
  conftest.py                       # shared fixtures + wait helpers
  mocks/
    __init__.py
    mock_camera_group.py            # MockCameraGroup, build_camera_configs_from_videos,
                                    #   _MockCameraGroupIPC, RealtimeLockstepDriver
  test_posthoc_calibration_pipeline.py
  test_posthoc_mocap_pipeline.py
  test_realtime_pipeline.py
```

## Component design

### `conftest.py`
Session-scoped fixtures (reuse the proven patterns from the current `test_e2e_pipeline.py`):
- `test_recording_path` → `Path(FREEMOCAP_TEST_DATA_PATH)`; `pytest.skip` if missing or no
  `synchronized_videos/*.mp4`. (`freemocap/system/default_paths.py`)
- `recording_info` → `RecordingInfo(recording_directory=str(path.parent), recording_name=path.stem, mic_device_index=-1)`.
- `global_kill_flag` → `multiprocessing.Value("b", False)`.
- `worker_registry` → `WorkerRegistry(global_kill_flag=..., worker_mode=WorkerMode.THREAD)`.
- `posthoc_manager` → `PosthocPipelineManager(global_kill_flag, worker_registry)`; teardown `shutdown()`.
- `charuco_board_7x5` → `CharucoBoardDefinition.create_test_data_7x5()`.
- `calibration_toml_path` (session, **prerequisite for mocap + realtime**): run
  `posthoc_manager.create_calibration_pipeline(recording_info, PosthocCalibrationPipelineConfig(charuco_board=create_test_data_7x5()))`,
  `_wait_for_pipeline()`, assert `get_last_successful_calibration_toml_path()` exists, return it.
- Helper `_wait_for_pipeline(pipeline, timeout=600)` polling `pipeline.alive`.

### `test_posthoc_calibration_pipeline.py`  (`@pytest.mark.e2e`)
Uses `calibration_toml_path`. Assertions:
- recording-local TOML `f"{stem}_camera_calibration.toml"` exists & non-empty.
- global last-successful TOML exists & non-empty.
- `annotated_videos/` count == source count; per-video width/height/frame-count match source
  (via `cv2.VideoCapture` props) — confirms 222 frames preserved.

### `test_posthoc_mocap_pipeline.py`  (`@pytest.mark.e2e`)
Depends on `calibration_toml_path`. Run mocap with Blender disabled:
`PosthocMocapPipelineConfig(calibration_source=MOST_RECENT, export_to_blender=False, auto_open_blend_file=False)`
via `posthoc_manager.create_mocap_pipeline(...)`, `_wait_for_pipeline()`. Assertions:
- `output_data/` has `*.npy` and `*.csv`.
- body 3D `.npy` is ≥2D, shape `(frames, points, 3)`-ish, and **not all-NaN** (triangulation worked).
- (variant) a second case with `calibration_source=SPECIFIED, calibration_toml_path=<fixture>`.

### `mocks/mock_camera_group.py`
- `build_camera_configs_from_videos(video_group) -> CameraConfigs`: one `CameraConfig` per video,
  `camera_id=<VideoGroupHelper key>`, unique `camera_index`, `resolution=ImageResolution(width=meta.width, height=meta.height)`,
  `color_channels=3`, `rotation=NO_ROTATION`. (`skellycam .../camera_config.py`, `image_resolution.py`)
- `_MockCameraGroupIPC` — minimal object exposing `global_kill_flag` (only field the pipeline reads).
- `MockCameraGroup` (duck-types `CameraGroup` for what `RealtimePipeline` uses):
  - `create(synchronized_videos_dir, global_kill_flag)`: build an **open** video group
    (`VideoGroupHelper.from_video_paths(paths, close_videos=False)`), build configs,
    `shm = CameraGroupSharedMemory.create(configs, TimebaseMapping(), read_only=False)`,
    `id = create_camera_group_id()`, `ipc=_MockCameraGroupIPC(global_kill_flag)`, `started=True`.
  - properties/methods used by the pipeline: `id`, `configs`, `shm`, `ipc`, `camera_ids`,
    `started`, `start()` (no-op). Optional faithful `get_latest_frontend_payload` /
    `get_frontend_payload_by_frame_number` delegating to `shm` + `create_frontend_payload`.
  - per-camera cached frame recarrays (built as in the recipe above).
  - `write_frame(n)`: per camera read `video_helper.read_frame_number(n)` (assert shape ==
    config image_shape), set `.image[0]`, `.frame_metadata.frame_number[0]=n`, timestamps, `put_frame(overwrite=True)`.
  - `close()`: `shm.unlink_and_close()`, video group `close()`.
- `RealtimeLockstepDriver(pipeline, mock_group)`:
  `run(num_frames, per_frame_timeout) -> list[AggregationNodeOutputMessage]`:
  for n in range(num_frames): `write_frame(n)`; drain/poll `pipeline.aggregation_output_subscription`
  until a message with `frame_number >= n` (timeout-guarded); `result_ready_event.clear();
  result_consumed_event.set()`; collect. Returns all outputs.

### `test_realtime_pipeline.py`  (`@pytest.mark.e2e`, parametrized)
Depends on `calibration_toml_path` (so realtime triangulation has a calibration on disk).
Two params:
- **charuco_only** (fast): `CameraNodeConfig(charuco_tracking_enabled=True, skeleton_tracking_enabled=False, worker_mode=THREAD, charuco_detector_config=CharucoDetectorConfig(board=create_test_data_7x5()))`, `use_centralized_gpu_inference=False`.
- **full_skeleton** (slow): `skeleton_tracking_enabled=True` (default RTMPose lightweight), `use_centralized_gpu_inference=False`.
Both: `RealtimePipelineConfig(camera_node_config=..., use_centralized_gpu_inference=False, log_pipeline_times=False)`; ensure `aggregator_config.triangulation_enabled=True` (verify defaults in `realtime_aggregator_node_config.py`).
Flow: `MockCameraGroup.create(...)` → `RealtimePipeline.create(camera_group=mock, worker_registry=thread_registry, pipeline_config=cfg)` → `.start()` → `RealtimeLockstepDriver.run(222, per_frame_timeout=...)`. Teardown: `pipeline.shutdown()`, `mock.close()`.
Assertions:
- received aggregation outputs for a large fraction of 222 frames; `frame_number`s monotonic.
- at least some frames have non-empty `keypoints_arrays` (3D triangulation succeeded) — charuco
  corners visible early (calibration segment) / body keypoints during movement.
- (full_skeleton) at least some frames carry `skeleton` (fitter) / `center_of_mass_result`.
- (optional) one `pipeline.get_latest_frontend_payload(...)` returns a non-None packet.

## Reused utilities (do not re-implement)
- Posthoc: `PosthocPipelineManager.{create_calibration_pipeline,create_mocap_pipeline}`, `PosthocPipeline.alive`.
- `VideoGroupHelper` / `VideoHelper` (`core/pipeline/posthoc/video_group_helper.py`) for reading frames.
- Configs: `PosthocCalibrationPipelineConfig`, `PosthocMocapPipelineConfig`, `RealtimePipelineConfig`, `CameraNodeConfig`.
- Board: `CharucoBoardDefinition.create_test_data_7x5()` (skellytracker).
- Calib paths: `get_last_successful_calibration_toml_path` (`core/tasks/calibration/shared/calibration_paths.py`).
- skellycam: `CameraGroupSharedMemory.create`, `CameraSharedMemoryRingBuffer.put_frame`,
  `CameraConfig`/`ImageResolution`/`validate_camera_configs`, `TimebaseMapping`, `create_frame_dtype`,
  `create_frontend_payload`, `WorkerRegistry`, `WorkerMode`, `RecordingInfo`, `create_camera_group_id`.

## Gotchas / risks
- Build the video group with `close_videos=False` so feeder reads work (default helpers close).
- camera_id consistency: posthoc calibration and the realtime mock both derive camera_ids from
  the same filename parsing, so calibration camera names resolve to runtime IDs.
- Feeder image shape must equal `config.image_shape` (build configs from actual video metadata).
- Flip `result_consumed_event`/`result_ready_event` in the driver to avoid aggregator stalls.
- Register the `e2e` marker (avoid PytestUnknownMarkWarning) and keep generous timeouts; full
  skeleton loads the RTMPose model.

## Cleanup
- Replace `freemocap/tests/test_e2e_pipeline.py`: its posthoc calibration/mocap/blender coverage
  is superseded by the new modules (with the correct 7x5 board). Delete it to keep a single
  source of truth (confirm with user before deleting).
- Register markers in `pyproject.toml` `[tool.pytest.ini_options]`:
  `markers = ["e2e: end-to-end tests requiring test data on disk"]`. Optionally add a
  `poe test-pipelines` task.

## Verification
- Fast plumbing: `uv run pytest freemocap/tests/pipelines/test_realtime_pipeline.py -k charuco_only -v -s --timeout=300`
- Posthoc: `uv run pytest freemocap/tests/pipelines/test_posthoc_calibration_pipeline.py freemocap/tests/pipelines/test_posthoc_mocap_pipeline.py -v -s --timeout=900`
- Full suite: `uv run pytest freemocap/tests/pipelines/ -v -s -m e2e --timeout=900`
- Confirm: calibration TOML(s) written; `output_data/*.npy` non-NaN body data; realtime driver
  reports outputs for most of the 222 frames with non-empty 3D keypoints.
```
```
