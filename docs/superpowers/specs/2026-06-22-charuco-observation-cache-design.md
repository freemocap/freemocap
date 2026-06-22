# Charuco Observation Cache: Reuse Realtime Detections in Posthoc Calibration

**Date:** 2026-06-22
**Status:** Design approved, pending implementation

## Context

When a calibration recording is started while a realtime pipeline is active, the `CameraNode` already runs full Charuco board detection on every frame (via `skellytracker.CharucoDetector.detect()`). These observations are published on the pubsub bus, consumed by the `RealtimeAggregatorNode` for triangulation and frontend display, and then **discarded**.

When the posthoc calibration pipeline runs afterward, each `VideoNode` re-reads the same frames from video files on disk and **re-runs the exact same Charuco detection** — effectively doing the same OpenCV work twice.

This spec describes a system to capture realtime Charuco observations during the calibration recording window and feed them into the posthoc pipeline, skipping redundant detection while preserving all frame synchronization guarantees.

## Design

### Architecture Overview

```
Calibration Recording (realtime active):
  CameraNode → detects Charuco → publishes CameraNodeOutputMessage
       │                              ↓
       │                    RealtimeAggregatorNode (display, unchanged)
       │
       └──→ CharucoRecorderNode [NEW]
              ↓
              buffers full CharucoObservation per (camera_id, frame_number)
              ↓
              on recording stop: pickle.dump → charuco_observations_realtime.pkl

Posthoc Calibration:
  VideoNode → cv2.VideoCapture.read() EVERY frame (unchanged)
       │
       ├── cache hit:  return pickled CharucoObservation (skip detect)
       └── cache miss: detector.detect(image) (normal path)
              ↓
  PosthocAggregatorNode (unchanged)
       ↓
  run_posthoc_calibration_task() (unchanged)
```

### New Components

#### 1. `CalibrationRecordingStateMessage` + `CalibrationRecordingStateTopic`

**File:** `freemocap/pubsub/pubsub_topics.py`

```python
@dataclass
class CalibrationRecordingStateMessage(TopicMessageABC):
    recording_info: RecordingInfo  # from skellycam
    is_active: bool

class CalibrationRecordingStateTopic(PubSubTopicABC):
    message_type = CalibrationRecordingStateMessage
```

Added to the pipeline's topic set. Published by the calibration HTTP endpoint on recording start/stop. Subscribed by the `CharucoRecorderNode`.

#### 2. `CharucoRecorderNode`

**File:** `freemocap/core/pipeline/realtime/charuco_recorder_node.py` (new)

A `SourceNode` that subscribes to `CameraNodeOutputTopic` and `CalibrationRecordingStateTopic`.

- **IDLE state:** Ignores camera outputs.
- **RECORDING state:** Appends `msg.charuco_observation` to `buffer[camera_id]` on every `CameraNodeOutputMessage`. Always appends — even when `charuco_empty=True` — so `buffer[camera_id][frame_N]` is the observation for frame N.
- **On recording stop:** Pickles the buffer plus metadata (`CharucoBoardDefinition`, frame range, recording UUID) to `{recording_path}/output_data/charuco_observations_realtime.pkl`.

#### 3. Cache-Aware `VideoNode`

**File:** `freemocap/core/pipeline/posthoc/video_node.py` (modified)

The `_run()` loop structure is **unchanged**. Every frame is read from video sequentially — no seeking, no skipping. The only change is how the observation is obtained:

```python
for frame_number in range(frame_count):
    success, image = video_reader.read()  # ALWAYS

    observation = _get_observation(
        frame_number=frame_number,
        image=image,
        detector=detector,
        cache=cache,
    )

    video_output_pub.put(VideoNodeOutputMessage(
        camera_id=camera_id,
        frame_number=frame_number,
        observation=observation,
    ))
```

```python
def _get_observation(frame_number, image, detector, cache):
    if cache is not None and frame_number in cache:
        return cache[frame_number]   # pickle-deserialized CharucoObservation
    return detector.detect(frame_number=frame_number, image=image)
```

`_try_load_cache()`:
1. Checks `charuco_observations_realtime.pkl` exists
2. Validates `CharucoBoardDefinition` matches current config
3. Returns `dict[int, CharucoObservation]` keyed by frame number
4. Returns `None` on any mismatch or missing file → seamless fallback

### Cache File Format

**Path:** `{recording_path}/output_data/charuco_observations_realtime.pkl`

**Format:** Python pickle containing:
```python
{
    "board_definition": CharucoBoardDefinition,
    "observations": {
        camera_id: list[CharucoObservation | None]  # indexed by frame_number
    },
    "frame_range": (int, int),
    "recording_uuid": str,
}
```

Full `CharucoObservation` objects — not a simplified format. Deserialization produces objects bit-identical to what `CharucoDetector.detect()` returns.

### Modified Components

| Component | File | Change |
|---|---|---|
| `CalibrationRecordingStateMessage` + Topic | `pubsub/pubsub_topics.py` | New topic + message type |
| `CharucoRecorderNode` | `core/pipeline/realtime/charuco_recorder_node.py` | New SourceNode |
| `RealtimePipeline` | `core/pipeline/realtime/realtime_pipeline.py` | Optionally creates CharucoRecorderNode |
| `calibration_router.py` | `api/http/calibration/calibration_router.py` | Publishes CalibrationRecordingStateMessage on start/stop |
| `video_node.py` | `core/pipeline/posthoc/video_node.py` | Cache lookup in `_run()` main loop |
| `posthoc_pipeline.py` | `core/pipeline/posthoc/posthoc_pipeline.py` | Passes recording path for cache lookup |

### Invariants

1. **Video frame sequencing is NEVER altered.** Every VideoNode reads every frame from `cv2.VideoCapture.read()` sequentially. No frame seeking. The cache only gates the `detector.detect()` call.
2. **One VideoNodeOutputMessage per frame per camera.** The PosthocAggregationNode sees the same message pattern regardless of cache usage.
3. **Graceful degradation.** If the realtime pipeline was not running during recording, or the cache file is missing, or the board config doesn't match — the VideoNode falls back to normal detection.
4. **Board config validated on load.** Cache is rejected if the pickled `CharucoBoardDefinition` doesn't match the calibration request's board config.

## Verification Plan

### Layer 1: Unit — CharucoRecorderNode
**File:** `freemocap/tests/pipelines/test_charuco_recorder.py` (new)

- Starts idle, ignores messages before recording signal
- Buffers observations (both detected and empty) during recording
- Frame index = list index invariant
- Flushes to pickle on recording stop
- Multiple cameras

### Layer 2: Unit — Cache-aware VideoNode
**File:** `freemocap/tests/pipelines/test_video_node_cache.py` (new)

- Loads cache when present and valid
- Falls back on missing/mismatched/corrupt cache
- Publishes sequential frames regardless of path
- CharucoObservation roundtrip fidelity through pickle

### Layer 3: Integration — Full pipeline E2E
**File:** `freemocap/tests/pipelines/test_calibration_cache_e2e.py` (new)

Uses existing infrastructure: `MockCameraGroup`, `drive_realtime_lockstep`, `freemocap_test_data` (7x5 charuco board, 3 cameras, 222 frames):

- `test_cache_path_produces_same_calibration_as_video_path` — TOML equivalence within tolerance
- `test_cache_is_faster_than_video` — wall-clock time reduced
- `test_graceful_fallback_when_no_cache` — normal video path succeeds

### Layer 4: Regression
All existing pipeline tests must continue to pass:
- `test_posthoc_calibration_pipeline.py`
- `test_realtime_pipeline.py` (charuco_only and full)
- `test_posthoc_mocap_pipeline.py`
- `test_anthropometry_validation.py`
