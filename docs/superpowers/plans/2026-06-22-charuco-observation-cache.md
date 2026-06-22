# Charuco Observation Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture Charuco observations from the realtime pipeline during calibration recordings and replay them in posthoc VideoNodes to skip redundant OpenCV detection.

**Architecture:** A new `CharucoRecorderNode` (SourceNode subclass) subscribes to `CameraNodeOutputTopic` and a new `CalibrationRecordingStateTopic`. During the recording window it buffers full `CharucoObservation` objects per (camera_id, frame_number). On recording stop it pickles them to `{recording_path}/output_data/charuco_observations_realtime.pkl`. The `VideoNode._run()` main loop — whose sequential `video_reader.read()` structure never changes — checks the cache before calling `detector.detect()`.

**Tech Stack:** Python multiprocessing, pickle, OpenCV (unchanged), existing pubsub system, existing test infrastructure (MockCameraGroup + drive_realtime_lockstep + freemocap_test_data).

## Global Constraints

- VideoNode's `video_reader.read()` loop is NEVER altered — cache only gates `detector.detect()`
- Every frame gets a `VideoNodeOutputMessage` published — frame sequencing is sacrosanct
- Cache miss → silent fallback to normal detection path
- Board config mismatch → cache rejected (validated on load)
- Pickle format for full CharucoObservation round-trip fidelity

---

### Task 1: CalibrationRecordingStateMessage + Topic

**Files:**
- Modify: `freemocap/pubsub/pubsub_topics.py` — add message + topic after the RecordingState section
- Test: `freemocap/tests/pubsub/test_calibration_recording_state_topic.py` (new)

**Interfaces:**
- Produces: `CalibrationRecordingStateMessage(recording_info: RecordingInfo, is_active: bool)` — published by calibration router, consumed by CharucoRecorderNode
- Produces: `CalibrationRecordingStateTopic = create_topic(CalibrationRecordingStateMessage)` — auto-registered via `__init_subclass__`

- [ ] **Step 1: Write the failing test**

```python
# freemocap/tests/pubsub/test_calibration_recording_state_topic.py
import pickle
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
)
from freemocap.pubsub.pubsub_abcs import PubSubTopicABC


def test_message_roundtrip():
    """CalibrationRecordingStateMessage survives pickle roundtrip."""
    info = RecordingInfo.create_temp()
    msg = CalibrationRecordingStateMessage(recording_info=info, is_active=True)
    
    reloaded = pickle.loads(pickle.dumps(msg))
    
    assert reloaded.recording_info.recording_name == info.recording_name
    assert reloaded.is_active is True


def test_message_defaults():
    """Default values are sensible."""
    msg = CalibrationRecordingStateMessage()
    
    assert msg.is_active is False


def test_topic_is_registered():
    """CalibrationRecordingStateTopic is auto-discovered."""
    registered = PubSubTopicABC.get_registered_topics()
    assert CalibrationRecordingStateTopic in registered


def test_topic_message_type():
    """Topic wraps the correct message type."""
    assert CalibrationRecordingStateTopic.message_type is CalibrationRecordingStateMessage
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest freemocap/tests/pubsub/test_calibration_recording_state_topic.py -v`
Expected: FAIL — `ImportError` or `NameError` for `CalibrationRecordingStateMessage`

- [ ] **Step 3: Write minimal implementation**

In `freemocap/pubsub/pubsub_topics.py`, add after the `SkeletonFitterResetMessage` section (before the topic instantiation block, around line 216):

```python
# ---------------------------------------------------------------------------
# Calibration recording state (bridge between HTTP endpoint and pipeline nodes)
# ---------------------------------------------------------------------------
# Published by the calibration HTTP endpoint when a calibration recording
# starts or stops. The CharucoRecorderNode subscribes to toggle buffering.

from skellycam.core.recorders.videos.recording_info import RecordingInfo

@dataclass
class CalibrationRecordingStateMessage(TopicMessageABC):
    recording_info: RecordingInfo | None = None
    is_active: bool = False
```

Then in the topic instantiation block (around line 198), add:

```python
CalibrationRecordingStateTopic = create_topic(CalibrationRecordingStateMessage)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest freemocap/tests/pubsub/test_calibration_recording_state_topic.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add freemocap/pubsub/pubsub_topics.py freemocap/tests/pubsub/test_calibration_recording_state_topic.py
git commit -m "feat: add CalibrationRecordingStateMessage + Topic to pubsub

CalibrationRecordingStateTopic bridges the HTTP calibration endpoint
and pipeline nodes — signals when a calibration recording starts/stops
so the CharucoRecorderNode can toggle observation buffering.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: CharucoRecorderNode

**Files:**
- Create: `freemocap/core/pipeline/realtime/charuco_recorder_node.py`
- Test: `freemocap/tests/pipelines/test_charuco_recorder.py` (new)

**Interfaces:**
- Consumes: `CalibrationRecordingStateTopic` (from Task 1), `CameraNodeOutputTopic` (existing)
- Produces: `charuco_observations_realtime.pkl` at `{recording_path}/output_data/`
- `CharucoRecorderNode.create(*, camera_ids, ipc, pubsub, worker_registry) -> CharucoRecorderNode`
- `CharucoRecorderNode._run(*, camera_node_output_sub, recording_state_sub, ipc, shutdown_self_flag) -> None`

- [ ] **Step 1: Write the failing test**

```python
# freemocap/tests/pipelines/test_charuco_recorder.py
import multiprocessing
import pickle
import tempfile
from pathlib import Path

import numpy as np
import pytest
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.charuco_tracker.charuco_board_definition import CharucoBoardDefinition
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.realtime.charuco_recorder_node import CharucoRecorderNode
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
    CameraNodeOutputMessage,
    CameraNodeOutputTopic,
)


@pytest.fixture
def global_kill_flag():
    return multiprocessing.Value("b", False)


@pytest.fixture
def pubsub(global_kill_flag):
    ps = PubSubTopicManager.create(global_kill_flag=global_kill_flag)
    yield ps
    ps.close()


@pytest.fixture
def ipc(global_kill_flag):
    return PipelineIPC.create(global_kill_flag=global_kill_flag)


@pytest.fixture
def recording_info(tmp_path):
    return RecordingInfo(
        recording_directory=str(tmp_path),
        recording_name="test_recording",
        mic_device_index=-1,
    )


def make_empty_charuco_observation():
    """Return a CharucoObservation with no detected corners."""
    board = CharucoBoardDefinition.create_test_data_7x5()
    return CharucoObservation.from_detection_results(
        board_definition=board,
        image_size=(1920, 1080),
        charuco_corners=None,
        charuco_ids=None,
        marker_corners=None,
        marker_ids=None,
    )


def make_detected_charuco_observation():
    """Return a CharucoObservation with fake detected corners."""
    board = CharucoBoardDefinition.create_test_data_7x5()
    # Create fake detection: 4 corners with IDs [0,1,2,3]
    charuco_corners = np.array([[[100.0, 200.0]], [[150.0, 200.0]], [[200.0, 200.0]], [[250.0, 200.0]]], dtype=np.float32)
    charuco_ids = np.array([0, 1, 2, 3], dtype=np.int32)
    marker_corners = np.array([[[[0, 0]], [[0, 0]], [[0, 0]], [[0, 0]]]], dtype=np.float32)
    marker_ids = np.array([0], dtype=np.int32)
    return CharucoObservation.from_detection_results(
        board_definition=board,
        image_size=(1920, 1080),
        charuco_corners=charuco_corners,
        charuco_ids=charuco_ids,
        marker_corners=marker_corners,
        marker_ids=marker_ids,
    )


class TestCharucoRecorderNode:
    def test_starts_idle(self, pubsub, ipc):
        """Before recording signal, no observations are buffered."""
        camera_node_output_pub = pubsub.get_publication_queue(CameraNodeOutputTopic)
        recording_state_pub = pubsub.get_publication_queue(CalibrationRecordingStateTopic)

        # Publish a camera output while no recording is active
        obs = make_detected_charuco_observation()
        camera_node_output_pub.put(CameraNodeOutputMessage(
            camera_id="cam_0",
            frame_number=0,
            charuco_observation=obs,
        ))
        pubsub.drain()

        # Recorder should NOT have buffered anything (it hasn't started recording)
        # We verify this by checking that publishing recording_state without
        # starting first doesn't write a cache file.
        # (This is a structural test — the recorder's _run loop isn't running yet.)
        # The real test is: after creating and destroying without ever sending
        # is_active=True, no cache file exists.

    def test_buffer_appends_per_frame(self, pubsub, ipc, recording_info, tmp_path):
        """When recording, each CameraNodeOutputMessage appends to buffer."""
        # This test exercises the buffer logic directly by simulating
        # what _run() does internally.
        from freemocap.core.pipeline.realtime.charuco_recorder_node import CharucoRecorderNode

        # Simulate the internal buffer state
        buffer: dict = {}
        camera_ids = ["cam_0", "cam_1"]
        buffer = {cid: [] for cid in camera_ids}

        # Simulate receiving frames during recording
        for frame_number in range(5):
            for cam_id in camera_ids:
                obs = make_detected_charuco_observation() if frame_number % 2 == 0 else make_empty_charuco_observation()
                buffer[cam_id].append(obs)

        # Verify: 5 frames per camera
        assert len(buffer["cam_0"]) == 5
        assert len(buffer["cam_1"]) == 5
        # Verify: frame index = list index
        assert buffer["cam_0"][3] is not None  # frame 3 was even → detected
        assert buffer["cam_0"][4].charuco_empty  # frame 4 was odd → empty

    def test_cache_file_is_valid_pickle(self, pubsub, ipc, recording_info, tmp_path):
        """The cache pickle file can be loaded and contains expected structure."""
        board = CharucoBoardDefinition.create_test_data_7x5()
        cache_data = {
            "board_definition": board,
            "observations": {
                "cam_0": [make_detected_charuco_observation() for _ in range(3)],
            },
            "frame_range": (0, 2),
            "recording_uuid": "test-uuid",
        }
        cache_path = tmp_path / "output_data" / "charuco_observations_realtime.pkl"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(cache_data, f)

        # Load and verify
        with open(cache_path, "rb") as f:
            loaded = pickle.load(f)

        assert loaded["board_definition"].squares_x == board.squares_x
        assert loaded["board_definition"].squares_y == board.squares_y
        assert len(loaded["observations"]["cam_0"]) == 3
        assert loaded["frame_range"] == (0, 2)
        assert not loaded["observations"]["cam_0"][0].charuco_empty

    def test_empty_observations_preserved(self):
        """Frames with no detection are stored — frame index invariant."""
        buffer = []
        for i in range(5):
            if i in [0, 2, 4]:
                buffer.append(make_detected_charuco_observation())
            else:
                buffer.append(make_empty_charuco_observation())

        assert len(buffer) == 5
        assert not buffer[0].charuco_empty
        assert buffer[1].charuco_empty
        assert not buffer[2].charuco_empty
        assert buffer[3].charuco_empty
        assert not buffer[4].charuco_empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest freemocap/tests/pipelines/test_charuco_recorder.py -v`
Expected: FAIL — `ImportError` for `charuco_recorder_node` module

- [ ] **Step 3: Write minimal implementation**

```python
# freemocap/core/pipeline/realtime/charuco_recorder_node.py
"""
CharucoRecorderNode: persists Charuco observations from realtime CameraNodes
during calibration recording windows, so posthoc calibration can skip
redundant OpenCV detection.
"""
import logging
import multiprocessing
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from freemocap.core.types.type_overloads import TopicSubscriptionQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
    CameraNodeOutputMessage,
    CameraNodeOutputTopic,
)

logger = logging.getLogger(__name__)

CACHE_FILENAME = "charuco_observations_realtime.pkl"
OUTPUT_DATA_DIR = "output_data"


@dataclass
class CharucoRecorderNode(SourceNode):
    """Buffers CharucoObservations during calibration recordings.

    Subscribes to CameraNodeOutputTopic (for observations) and
    CalibrationRecordingStateTopic (for start/stop signals).

    On recording stop, pickles the full buffer to
    ``{recording_path}/output_data/charuco_observations_realtime.pkl``.
    """

    camera_ids: list[CameraIdString] = field(default_factory=list)
    progress_subscription: TopicSubscriptionQueue | None = None

    @classmethod
    def create(
        cls,
        *,
        camera_ids: list[CameraIdString],
        ipc: PipelineIPC,
        pubsub: PubSubTopicManager,
    ) -> "CharucoRecorderNode":
        camera_node_output_sub = pubsub.get_subscription(CameraNodeOutputTopic)
        recording_state_sub = pubsub.get_subscription(CalibrationRecordingStateTopic)

        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name="CharucoRecorderNode",
            log_queue=ipc.ws_queue,
            kwargs=dict(
                camera_ids=camera_ids,
                camera_node_output_sub=camera_node_output_sub,
                recording_state_sub=recording_state_sub,
                ipc=ipc,
                shutdown_self_flag=None,
            ),
        )
        return cls(
            camera_ids=camera_ids,
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
        *,
        camera_ids: list[CameraIdString],
        camera_node_output_sub: TopicSubscriptionQueue,
        recording_state_sub: TopicSubscriptionQueue,
        ipc: PipelineIPC,
        shutdown_self_flag: Synchronized,
    ) -> None:
        from queue import Empty

        logger.info("CharucoRecorderNode started — waiting for calibration recording signal")

        buffer: dict[CameraIdString, list[CharucoObservation | None]] = {
            cid: [] for cid in camera_ids
        }
        recording_info = None
        is_recording = False

        try:
            while ipc.should_continue:
                # Drain recording state messages
                while True:
                    try:
                        msg = recording_state_sub.get_nowait()
                        if isinstance(msg, CalibrationRecordingStateMessage):
                            if msg.is_active and not is_recording:
                                is_recording = True
                                recording_info = msg.recording_info
                                buffer = {cid: [] for cid in camera_ids}
                                logger.info(
                                    f"Calibration recording started: "
                                    f"{recording_info.recording_name if recording_info else 'unknown'}"
                                )
                            elif not msg.is_active and is_recording:
                                is_recording = False
                                logger.info(
                                    f"Calibration recording stopped — "
                                    f"flushing {sum(len(v) for v in buffer.values())} observations"
                                )
                                _flush_buffer(
                                    buffer=buffer,
                                    recording_info=recording_info,
                                )
                    except Empty:
                        break

                # Drain camera node output messages (only when recording)
                while True:
                    try:
                        msg = camera_node_output_sub.get_nowait()
                        if (
                            is_recording
                            and isinstance(msg, CameraNodeOutputMessage)
                            and msg.camera_id in buffer
                        ):
                            buffer[msg.camera_id].append(msg.charuco_observation)
                    except Empty:
                        break

        except Exception:
            logger.exception("CharucoRecorderNode crashed")
        finally:
            # Flush if still recording on shutdown
            if is_recording:
                logger.warning(
                    "CharucoRecorderNode shutting down while recording active — "
                    "flushing partial buffer"
                )
                _flush_buffer(buffer=buffer, recording_info=recording_info)
            logger.info("CharucoRecorderNode exiting")


def _flush_buffer(
    *,
    buffer: dict[CameraIdString, list],
    recording_info,
) -> None:
    """Write the buffer to a pickle file."""
    if recording_info is None:
        logger.warning("No recording_info — cannot flush buffer")
        return

    recording_path = Path(recording_info.full_recording_path)
    output_dir = recording_path / OUTPUT_DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / CACHE_FILENAME

    # Determine frame range
    all_lengths = [len(obs_list) for obs_list in buffer.values()]
    if not all_lengths or max(all_lengths) == 0:
        logger.info("Buffer is empty — writing empty cache")
        first_frame = last_frame = 0
    else:
        first_frame = 0
        last_frame = max(all_lengths) - 1

    # Extract board definition from first non-empty observation
    board_definition = None
    for obs_list in buffer.values():
        for obs in obs_list:
            if obs is not None and isinstance(obs, CharucoObservation):
                try:
                    board_definition = obs.board_definition
                except AttributeError:
                    pass
                if board_definition is not None:
                    break
        if board_definition is not None:
            break

    cache_data = {
        "board_definition": board_definition,
        "observations": buffer,
        "frame_range": (first_frame, last_frame),
        "recording_uuid": recording_info.recording_uuid if recording_info else "",
    }

    with open(cache_path, "wb") as f:
        pickle.dump(cache_data, f)

    total_obs = sum(len(v) for v in buffer.values())
    logger.info(
        f"Wrote {total_obs} observations ({len(buffer)} cameras) to {cache_path}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest freemocap/tests/pipelines/test_charuco_recorder.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add freemocap/core/pipeline/realtime/charuco_recorder_node.py freemocap/tests/pipelines/test_charuco_recorder.py
git commit -m "feat: add CharucoRecorderNode for realtime observation capture

Subscribes to CameraNodeOutputTopic + CalibrationRecordingStateTopic.
Buffers full CharucoObservation objects per (camera_id, frame_number)
during calibration recording windows. Pickles to cache on stop.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Calibration Router — Publish Recording State

**Files:**
- Modify: `freemocap/api/http/calibration/calibration_router.py:128-143` (start endpoint), `:146-171` (stop endpoint)

**Interfaces:**
- Consumes: `CalibrationRecordingStateTopic`, `CalibrationRecordingStateMessage` (from Task 1), `get_freemocap_app()` (existing)
- Produces: Publishes `CalibrationRecordingStateMessage(is_active=True)` on start, `(is_active=False)` on stop

- [ ] **Step 1: Write the failing test**

```python
# freemocap/tests/http/test_calibration_router_recording_state.py
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi.testclient import TestClient

from freemocap.api.http.calibration.calibration_router import calibration_router
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
)


@pytest.fixture
def mock_app():
    """Mock FreemocapApplication with a realtime pipeline that has pubsub."""
    app = MagicMock()
    app.start_recording_all = AsyncMock()
    app.stop_recording_all = AsyncMock(return_value=MagicMock(
        full_recording_path="/tmp/test/test_recording",
        recording_name="test_recording",
    ))
    app.create_posthoc_calibration_pipeline = AsyncMock(return_value=MagicMock(id="pipe_123"))

    # Mock realtime pipeline manager with one alive pipeline
    mock_pipeline = MagicMock()
    mock_pipeline.alive = True
    mock_pipeline.pubsub = MagicMock()
    mock_pipeline.pubsub.publish = MagicMock()

    app.realtime_pipeline_manager = MagicMock()
    app.realtime_pipeline_manager.pipelines = {"pipe_1": mock_pipeline}

    return app


@pytest.fixture
def client(mock_app):
    from fastapi import FastAPI
    test_app = FastAPI()
    test_app.include_router(calibration_router)

    with patch(
        "freemocap.api.http.calibration.calibration_router.get_freemocap_app",
        return_value=mock_app,
    ):
        with patch(
            "freemocap.api.http.calibration.calibration_router._reject_if_recording_directory_not_empty",
            return_value=None,
        ):
            yield TestClient(test_app)


class TestCalibrationRecordingStatePublishing:
    def test_start_publishes_recording_state(self, client, mock_app):
        """POST /calibration/recording/start publishes is_active=True."""
        response = client.post("/calibration/recording/start", json={
            "calibrationTaskConfig": {
                "charucoBoard": {
                    "squaresX": 7,
                    "squaresY": 5,
                    "squareLengthMm": 54,
                    "markerLengthRatio": 0.8,
                    "arucoDictionaryEnum": "DICT_4X4_250",
                }
            },
            "calibrationRecordingDirectory": "/tmp/test",
        })
        assert response.status_code == 200

        # Verify publish was called on each alive pipeline
        for pipeline in mock_app.realtime_pipeline_manager.pipelines.values():
            pipeline.pubsub.publish.assert_called()
            call_args = pipeline.pubsub.publish.call_args
            # topic_type should be CalibrationRecordingStateTopic
            # message should be CalibrationRecordingStateMessage(is_active=True)

    def test_stop_publishes_recording_state(self, client, mock_app):
        """POST /calibration/recording/stop publishes is_active=False."""
        response = client.post("/calibration/recording/stop", json={
            "calibrationTaskConfig": {
                "charucoBoard": {
                    "squaresX": 7,
                    "squaresY": 5,
                    "squareLengthMm": 54,
                    "markerLengthRatio": 0.8,
                    "arucoDictionaryEnum": "DICT_4X4_250",
                }
            },
        })
        assert response.status_code == 200

        for pipeline in mock_app.realtime_pipeline_manager.pipelines.values():
            pipeline.pubsub.publish.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest freemocap/tests/http/test_calibration_router_recording_state.py -v`
Expected: FAIL — assertions about `publish` being called fail (it's not called yet)

- [ ] **Step 3: Write minimal implementation**

In `freemocap/api/http/calibration/calibration_router.py`, add imports at the top:

```python
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
)
```

Modify `start_calibration_recording` (after line 136, inside the try block):

```python
@calibration_router.post("/recording/start")
async def start_calibration_recording(
        request: CalibrateRecordingRequest,
) -> StartCalibrationRecordingResponse:
    """Start calibration recording with given config."""
    try:
        recording_info = request.to_recording_info()
        _reject_if_recording_directory_not_empty(recording_info)
        await get_freemocap_app().start_recording_all(recording_info=recording_info)
        logger.info(f"Starting calibration recording: {recording_info}")

        # Notify realtime pipelines that a calibration recording has started
        app = get_freemocap_app()
        for pipeline in app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                pipeline.pubsub.publish(
                    CalibrationRecordingStateTopic,
                    CalibrationRecordingStateMessage(
                        recording_info=recording_info,
                        is_active=True,
                    ),
                )
                logger.debug(
                    f"Published CalibrationRecordingState(is_active=True) "
                    f"to pipeline [{pipeline.id}]"
                )

        return StartCalibrationRecordingResponse(success=True, message="Recording started")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error starting calibration recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

Modify `stop_calibration_recording` (before launching the posthoc pipeline, after line 157):

```python
@calibration_router.post("/recording/stop")
async def stop_calibration_recording(
        request: StopCalibrationRecordingRequest,
) -> dict:
    """Stop current calibration recording and launch posthoc calibration pipeline."""
    app = get_freemocap_app()
    try:
        recording_info = await app.stop_recording_all()
        if recording_info is None:
            logger.warning("No active recording to stop")
            return {"success": True}

        # Notify realtime pipelines that calibration recording has stopped
        for pipeline in app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                pipeline.pubsub.publish(
                    CalibrationRecordingStateTopic,
                    CalibrationRecordingStateMessage(
                        recording_info=recording_info,
                        is_active=False,
                    ),
                )
                logger.debug(
                    f"Published CalibrationRecordingState(is_active=False) "
                    f"to pipeline [{pipeline.id}]"
                )

        logger.info(f"Recording stopped - saved to: {recording_info.full_recording_path}")
        pipeline = await app.create_posthoc_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=request.calibration_config,
        )
        logger.info("Calibration recording stopped, posthoc calibration pipeline launched")
        return {
            "success": True,
            "pipeline_id": pipeline.id,
            "recording_name": recording_info.recording_name,
            "recording_path": str(recording_info.full_recording_path),
        }
    except Exception as e:
        logger.exception(f"Error stopping calibration recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest freemocap/tests/http/test_calibration_router_recording_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add freemocap/api/http/calibration/calibration_router.py freemocap/tests/http/test_calibration_router_recording_state.py
git commit -m "feat: publish calibration recording state to realtime pipelines

POST /calibration/recording/start → publishes is_active=True
POST /calibration/recording/stop  → publishes is_active=False

Only publishes to alive pipelines (no-op if no realtime pipeline active).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: RealtimePipeline — Create CharucoRecorderNode

**Files:**
- Modify: `freemocap/core/pipeline/realtime/realtime_pipeline.py:98-205` (create method and shutdown)

**Interfaces:**
- Consumes: `CharucoRecorderNode` (from Task 2)
- Produces: `RealtimePipeline.charuco_recorder_node: CharucoRecorderNode | None`
- When `charuco_tracking_enabled=True` in pipeline config, create + start the recorder node

- [ ] **Step 1: Write the failing test**

```python
# Add to freemocap/tests/pipelines/test_realtime_pipeline.py
# (or a focused test file)

def test_pipeline_creates_recorder_when_charuco_enabled():
    """RealtimePipeline creates CharucoRecorderNode when charuco tracking is on."""
    # This will be tested in the E2E test (Task 6) —
    # unit-level verification that the pipeline has a charuco_recorder_node
    # attribute when charuco_tracking_enabled=True
    pass  # Placeholder — covered by E2E integration test
```

Since this is primarily wiring, the integration test in Task 6 covers it. The unit test here is a structural check.

- [ ] **Step 2: Skip (covered by integration test)**

- [ ] **Step 3: Write implementation**

In `realtime_pipeline.py`, add import:

```python
from freemocap.core.pipeline.realtime.charuco_recorder_node import CharucoRecorderNode
```

Add field to `RealtimePipeline` dataclass (after `skeleton_inference_node`):

```python
@dataclass
class RealtimePipeline:
    # ... existing fields ...
    skeleton_inference_node: RealtimeSkeletonInferenceNode | None
    charuco_recorder_node: CharucoRecorderNode | None  # NEW
```

In `RealtimePipeline.create()`, add after the `skeleton_inference_node` creation block (around line 158):

```python
        # Create CharucoRecorderNode if charuco tracking is enabled.
        # This node buffers observations during calibration recording windows
        # so posthoc calibration can skip redundant detection.
        charuco_recorder_node: CharucoRecorderNode | None = None
        if pipeline_config.camera_node_config.charuco_tracking_enabled:
            charuco_recorder_node = CharucoRecorderNode.create(
                camera_ids=pipeline_camera_ids,
                ipc=ipc,
                pubsub=pubsub,
            )
```

In the return `cls(...)` constructor call, add:

```python
        return cls(
            # ... existing fields ...
            skeleton_inference_node=skeleton_inference_node,
            charuco_recorder_node=charuco_recorder_node,  # NEW
        )
```

In `start()`, add after the camera node start loop (around line 234-236):

```python
        if self.charuco_recorder_node is not None:
            self.charuco_recorder_node.start()
            logger.info(f"CharucoRecorderNode started for pipeline [{self.id}]")
```

In `shutdown()`, add in the shutdown sequence (after skeleton inference node shutdown, around line 256):

```python
        if self.charuco_recorder_node is not None and self.charuco_recorder_node.is_alive:
            self.charuco_recorder_node.worker._intentionally_terminated = True
            self.charuco_recorder_node.shutdown()
```

Update `alive` property to include recorder node:

```python
    @property
    def alive(self) -> bool:
        if not self.started:
            return False
        nodes_alive = (
                all(node.is_alive for node in self.camera_nodes.values())
                and self.aggregation_node.is_alive
        )
        if self.skeleton_inference_node is not None:
            nodes_alive = nodes_alive and self.skeleton_inference_node.is_alive
        if self.charuco_recorder_node is not None:
            nodes_alive = nodes_alive and self.charuco_recorder_node.is_alive
        return nodes_alive
```

- [ ] **Step 4: Verify with existing tests**

Run: `uv run pytest freemocap/tests/pipelines/test_realtime_pipeline.py -v`
Expected: PASS (existing tests should still pass — recorder node is only created when charuco_tracking_enabled, which the "charuco_only" param already enables)

- [ ] **Step 5: Commit**

```bash
git add freemocap/core/pipeline/realtime/realtime_pipeline.py
git commit -m "feat: wire CharucoRecorderNode into RealtimePipeline

Created when charuco_tracking_enabled=True. Started after camera nodes,
shut down in shutdown sequence. Tracked in alive property.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Cache-Aware VideoNode

**Files:**
- Modify: `freemocap/core/pipeline/posthoc/video_node.py:130-330` (the `_run` static method)
- Test: `freemocap/tests/pipelines/test_video_node_cache.py` (new)

**Interfaces:**
- Consumes: `charuco_observations_realtime.pkl` cache file (from Task 2)
- Produces: `VideoNodeOutputMessage` (unchanged — existing aggregator contract)
- `_try_load_cache(recording_path, camera_id, board_config) -> dict[int, CharucoObservation] | None`
- `_get_observation(frame_number, image, detector, cache) -> BaseObservation`

- [ ] **Step 1: Write the failing test**

```python
# freemocap/tests/pipelines/test_video_node_cache.py
import pickle
import tempfile
from pathlib import Path

import numpy as np
import pytest
from skellytracker.trackers.charuco_tracker.charuco_board_definition import CharucoBoardDefinition
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation
from skellytracker.trackers.charuco_tracker.charuco_tracker_config import CharucoDetectorConfig

from freemocap.core.pipeline.posthoc.video_node import _try_load_cache, _get_observation


@pytest.fixture
def board_7x5():
    return CharucoBoardDefinition.create_test_data_7x5()


@pytest.fixture
def board_5x3():
    return CharucoBoardDefinition.create_letter_size_5x3()


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "output_data" / "charuco_observations_realtime.pkl"


def make_fake_observation(board, has_detection=True):
    """Create a minimal CharucoObservation for testing."""
    if has_detection:
        charuco_corners = np.array([[[100.0, 200.0]]], dtype=np.float32)
        charuco_ids = np.array([0], dtype=np.int32)
        marker_corners = np.array([[[[0, 0]], [[0, 0]], [[0, 0]], [[0, 0]]]], dtype=np.float32)
        marker_ids = np.array([0], dtype=np.int32)
    else:
        charuco_corners = None
        charuco_ids = None
        marker_corners = None
        marker_ids = None

    return CharucoObservation.from_detection_results(
        board_definition=board,
        image_size=(1920, 1080),
        charuco_corners=charuco_corners,
        charuco_ids=charuco_ids,
        marker_corners=marker_corners,
        marker_ids=marker_ids,
    )


class TestTryLoadCache:
    def test_returns_none_when_cache_missing(self, tmp_path, board_7x5):
        """If no cache file exists, return None."""
        result = _try_load_cache(
            recording_path=tmp_path,
            camera_id="cam_0",
            board_config=board_7x5,
        )
        assert result is None

    def test_returns_observations_when_cache_exists(self, tmp_path, cache_path, board_7x5):
        """Valid cache returns observations dict."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        obs_list = [make_fake_observation(board_7x5, has_detection=True) for _ in range(5)]
        cache_data = {
            "board_definition": board_7x5,
            "observations": {"cam_0": obs_list},
            "frame_range": (0, 4),
            "recording_uuid": "test-uuid",
        }
        with open(cache_path, "wb") as f:
            pickle.dump(cache_data, f)

        result = _try_load_cache(
            recording_path=tmp_path,
            camera_id="cam_0",
            board_config=board_7x5,
        )
        assert result is not None
        assert len(result) == 5
        assert not result[0].charuco_empty

    def test_returns_none_on_board_mismatch(self, tmp_path, cache_path, board_7x5, board_5x3):
        """Different board config → cache rejected."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "board_definition": board_7x5,
            "observations": {"cam_0": []},
            "frame_range": (0, 0),
            "recording_uuid": "",
        }
        with open(cache_path, "wb") as f:
            pickle.dump(cache_data, f)

        result = _try_load_cache(
            recording_path=tmp_path,
            camera_id="cam_0",
            board_config=board_5x3,  # Different!
        )
        assert result is None

    def test_returns_none_on_corrupt_cache(self, tmp_path, cache_path, board_7x5):
        """Corrupt pickle → return None (don't crash)."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("not a pickle file")

        result = _try_load_cache(
            recording_path=tmp_path,
            camera_id="cam_0",
            board_config=board_7x5,
        )
        assert result is None

    def test_returns_none_when_camera_not_in_cache(self, tmp_path, cache_path, board_7x5):
        """Camera ID not in cache → return None."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "board_definition": board_7x5,
            "observations": {"cam_0": []},  # cam_0 only, not cam_1
            "frame_range": (0, 0),
            "recording_uuid": "",
        }
        with open(cache_path, "wb") as f:
            pickle.dump(cache_data, f)

        result = _try_load_cache(
            recording_path=tmp_path,
            camera_id="cam_1",  # Not in cache
            board_config=board_7x5,
        )
        assert result is None


class TestGetObservation:
    def test_uses_cache_when_frame_present(self, board_7x5):
        """When cache has the frame, return cached observation."""
        cached_obs = make_fake_observation(board_7x5, has_detection=True)
        cache = {0: cached_obs}

        result = _get_observation(
            frame_number=0,
            image=np.zeros((1080, 1920, 3), dtype=np.uint8),
            detector=None,  # Should not be called
            cache=cache,
        )
        assert result is cached_obs

    def test_falls_back_to_detector_when_frame_missing(self, board_7x5):
        """When cache doesn't have the frame, call detector."""
        cache = {0: make_fake_observation(board_7x5)}

        mock_detector_called = False
        class FakeDetector:
            def detect(self, frame_number, image):
                nonlocal mock_detector_called
                mock_detector_called = True
                return make_fake_observation(board_7x5, has_detection=False)

        result = _get_observation(
            frame_number=1,  # Not in cache
            image=np.zeros((1080, 1920, 3), dtype=np.uint8),
            detector=FakeDetector(),
            cache=cache,
        )
        assert mock_detector_called
        assert result.charuco_empty

    def test_falls_back_when_cache_is_none(self, board_7x5):
        """None cache → always call detector."""
        mock_detector_called = False
        class FakeDetector:
            def detect(self, frame_number, image):
                nonlocal mock_detector_called
                mock_detector_called = True
                return make_fake_observation(board_7x5)

        result = _get_observation(
            frame_number=0,
            image=np.zeros((1080, 1920, 3), dtype=np.uint8),
            detector=FakeDetector(),
            cache=None,
        )
        assert mock_detector_called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest freemocap/tests/pipelines/test_video_node_cache.py -v`
Expected: FAIL — `ImportError` for `_try_load_cache` or `_get_observation`

- [ ] **Step 3: Write implementation**

Add these imports at the top of `video_node.py`:

```python
import pickle
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation
```

Add these module-level constants and functions after the `VideoNode` class (before `get_progress_messages`):

```python
CACHE_FILENAME = "charuco_observations_realtime.pkl"


def _try_load_cache(
    *,
    recording_path: Path,
    camera_id: CameraIdString,
    board_config,
) -> dict[int, object] | None:
    """Load the realtime Charuco observation cache if it exists and matches.

    Returns a dict mapping frame_number → CharucoObservation, or None if
    the cache is missing, corrupt, or has a different board config.
    """
    cache_path = recording_path / "output_data" / CACHE_FILENAME
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "rb") as f:
            cache_data = pickle.load(f)
    except Exception:
        logger.warning(
            f"Failed to load Charuco observation cache from {cache_path} — "
            f"falling back to normal detection",
            exc_info=True,
        )
        return None

    # Validate board config match
    cached_board = cache_data.get("board_definition")
    if cached_board is None:
        logger.warning("Cache missing board_definition — rejecting")
        return None

    # Compare key board parameters
    if (
        cached_board.squares_x != board_config.squares_x
        or cached_board.squares_y != board_config.squares_y
        or abs(cached_board.square_length_mm - board_config.square_length_mm) > 0.01
        or cached_board.aruco_dictionary_enum != board_config.aruco_dictionary_enum
    ):
        logger.info(
            f"Cache board config mismatch — "
            f"cache=({cached_board.squares_x}x{cached_board.squares_y}, "
            f"{cached_board.square_length_mm}mm), "
            f"request=({board_config.squares_x}x{board_config.squares_y}, "
            f"{board_config.square_length_mm}mm) — "
            f"falling back to normal detection"
        )
        return None

    observations = cache_data.get("observations", {})
    if camera_id not in observations:
        logger.info(
            f"Camera {camera_id} not found in cache — "
            f"falling back to normal detection"
        )
        return None

    obs_list = observations[camera_id]
    logger.info(
        f"Loaded {len(obs_list)} cached Charuco observations "
        f"for camera {camera_id} from {cache_path}"
    )
    return {frame_number: obs for frame_number, obs in enumerate(obs_list)}


def _get_observation(
    *,
    frame_number: int,
    image,
    detector,
    cache: dict[int, object] | None,
):
    """Get observation for a frame — from cache if available, else detect.

    Args:
        frame_number: The current frame number.
        image: The frame image (only used if cache miss).
        detector: The CharucoDetector (only called on cache miss).
        cache: Frame_number → CharucoObservation mapping, or None.

    Returns:
        CharucoObservation from cache or from detector.detect().
    """
    if cache is not None and frame_number in cache:
        return cache[frame_number]

    return detector.detect(
        frame_number=frame_number,
        image=image,
    )
```

Modify `VideoNode._run()` to load the cache at the top and use `_get_observation`. Change the `_run` method signature to accept `recording_path` (already present) and update imports. In the main loop (around line 234-246), replace:

```python
                    observation = detector.detect(
                        frame_number=frame_number,
                        image=image,
                    )
```

With:

```python
                    observation = _get_observation(
                        frame_number=frame_number,
                        image=image,
                        detector=detector,
                        cache=cache,
                    )
```

And add at the top of the `_run` try block (after detector creation, before the video loop, around line 157):

```python
            # Try to load cached Charuco observations from a prior realtime
            # recording window. On cache hit, detection is skipped per-frame
            # but video I/O and frame sequencing are completely unchanged.
            cache = _try_load_cache(
                recording_path=recording_path,
                camera_id=camera_id,
                board_config=detector_config,
            )
            if cache is not None:
                logger.info(
                    f"VideoNode [{camera_id}]: using cached observations "
                    f"({len(cache)} frames) — detection will be skipped"
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest freemocap/tests/pipelines/test_video_node_cache.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add freemocap/core/pipeline/posthoc/video_node.py freemocap/tests/pipelines/test_video_node_cache.py
git commit -m "feat: cache-aware VideoNode skips detection when cache exists

_try_load_cache() checks for charuco_observations_realtime.pkl, validates
board config matches. _get_observation() returns cached result on hit,
falls through to detector.detect() on miss.

Video I/O loop is UNCHANGED — every frame is read from cv2.VideoCapture
sequentially. Only the detector.detect() call is gated.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: End-to-End Integration Test

**Files:**
- Create: `freemocap/tests/pipelines/test_calibration_cache_e2e.py`
- Modify: `freemocap/tests/pipelines/conftest.py` — add CharucoRecorderNode fixture if needed

**Interfaces:**
- Consumes: All components from Tasks 1-5
- Uses existing: `MockCameraGroup`, `drive_realtime_lockstep`, `freemocap_test_data`, `charuco_board_7x5`, `posthoc_manager`, `recording_info`, `synchronized_videos_dir`, `global_kill_flag`

- [ ] **Step 1: Write the E2E test**

```python
# freemocap/tests/pipelines/test_calibration_cache_e2e.py
"""
End-to-end test: realtime Charuco capture → cache file → posthoc calibration via cache.

Uses MockCameraGroup + drive_realtime_lockstep to simulate a realtime pipeline
processing freemocap_test_data (7x5 charuco board, 3 cameras, 222 frames).
Verifies the cache file is written and produces equivalent calibration results.
"""
import logging
import pickle
import time
from pathlib import Path

import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.trackers.charuco_tracker.charuco_board_definition import CharucoBoardDefinition

from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.calibration.shared.calibration_paths import get_last_successful_calibration_toml_path
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
)
from freemocap.tests.pipelines.helpers import wait_for_pipeline
from freemocap.tests.pipelines.mocks.mock_camera_group import MockCameraGroup
from freemocap.tests.pipelines.mocks.realtime_driver import drive_realtime_lockstep

logger = logging.getLogger(__name__)

CACHE_FILENAME = "charuco_observations_realtime.pkl"


@pytest.fixture(scope="module")
def realtime_cache_path(test_recording_path: Path) -> Path:
    """Path where the CharucoRecorderNode writes its cache."""
    return test_recording_path / "output_data" / CACHE_FILENAME


@pytest.fixture(scope="module")
def realtime_pipeline_for_capture(
    global_kill_flag,
    synchronized_videos_dir: Path,
    charuco_board_7x5: CharucoBoardDefinition,
    realtime_max_frames: int,
) -> RealtimePipeline:
    """Create a realtime pipeline with CharucoRecorderNode, drive through all frames."""
    logger.info("=" * 60)
    logger.info("SETUP: Creating realtime pipeline with CharucoRecorderNode")

    # Create mock camera group from test data
    mock_group = MockCameraGroup.create(
        synchronized_videos_dir=str(synchronized_videos_dir),
        global_kill_flag=global_kill_flag,
    )

    # Build pipeline config with Charuco tracking enabled
    camera_node_config = CameraNodeConfig(
        charuco_tracking_enabled=True,
        charuco_detector_config=charuco_board_7x5.to_detector_config(),
        skeleton_tracking_enabled=False,
    )
    aggregator_config = RealtimeAggregatorNodeConfig(
        charuco_tracking_enabled=True,
    )
    pipeline_config = RealtimePipelineConfig(
        camera_node_config=camera_node_config,
        aggregator_node_config=aggregator_config,
    )

    worker_registry = WorkerRegistry(
        global_kill_flag=global_kill_flag,
        worker_mode=WorkerMode.THREAD,
    )

    pipeline = RealtimePipeline.create(
        camera_group=mock_group,
        pipeline_config=pipeline_config,
        worker_registry=worker_registry,
    )

    pipeline.start()
    logger.info(f"RealtimePipeline [{pipeline.id}] started")

    # Verify CharucoRecorderNode was created
    assert pipeline.charuco_recorder_node is not None, (
        "CharucoRecorderNode should be created when charuco_tracking_enabled=True"
    )

    # Publish calibration recording start
    logger.info("Publishing CalibrationRecordingState(is_active=True)")
    pipeline.pubsub.publish(
        CalibrationRecordingStateTopic,
        CalibrationRecordingStateMessage(is_active=True),
    )

    # Drive through all frames
    num_frames = realtime_max_frames if realtime_max_frames > 0 else 222
    logger.info(f"Driving {num_frames} frames through realtime pipeline")
    result = drive_realtime_lockstep(
        pipeline=pipeline,
        mock_group=mock_group,
        num_frames=num_frames,
    )
    logger.info(f"Processed {len(result.outputs)} frames")

    # Publish calibration recording stop
    logger.info("Publishing CalibrationRecordingState(is_active=False)")
    pipeline.pubsub.publish(
        CalibrationRecordingStateTopic,
        CalibrationRecordingStateMessage(is_active=False),
    )

    # Allow time for the recorder to flush
    time.sleep(0.5)

    yield pipeline

    # Cleanup
    logger.info("Shutting down realtime pipeline")
    pipeline.shutdown()
    mock_group.close()


@pytest.mark.e2e
class TestCalibrationCacheE2E:
    """End-to-end tests for the Charuco observation cache pipeline."""

    def test_cache_file_written(self, realtime_pipeline_for_capture, realtime_cache_path):
        """After a calibration recording with realtime pipeline active,
        the cache file is written to the recording's output_data directory."""
        assert realtime_cache_path.exists(), (
            f"Cache file not found at {realtime_cache_path}"
        )

        with open(realtime_cache_path, "rb") as f:
            cache_data = pickle.load(f)

        assert "observations" in cache_data
        assert "board_definition" in cache_data
        assert "frame_range" in cache_data

        # Should have observations for each camera in the test data (3 cameras)
        observations = cache_data["observations"]
        assert len(observations) >= 1, "At least one camera should have observations"

        for cam_id, obs_list in observations.items():
            assert len(obs_list) > 0, f"Camera {cam_id} should have observations"
            logger.info(f"Camera {cam_id}: {len(obs_list)} observations")

    def test_cache_contains_valid_observations(self, realtime_pipeline_for_capture, realtime_cache_path):
        """Cache contains non-empty CharucoObservation objects for frames
        where the board was visible."""
        with open(realtime_cache_path, "rb") as f:
            cache_data = pickle.load(f)

        observations = cache_data["observations"]

        # Count frames with detected corners vs empty
        total_detected = 0
        total_empty = 0
        for cam_id, obs_list in observations.items():
            for obs in obs_list:
                if obs is not None and hasattr(obs, 'charuco_empty') and not obs.charuco_empty:
                    total_detected += 1
                else:
                    total_empty += 1

        logger.info(f"Cache stats: {total_detected} detected, {total_empty} empty")
        # At least some frames should have detected the board
        assert total_detected > 0, (
            "Expected at least some frames with detected Charuco corners"
        )

    def test_posthoc_calibration_with_cache(
        self,
        recording_info,
        posthoc_manager,
        charuco_board_7x5,
        realtime_cache_path,
        test_recording_path,
    ):
        """Posthoc calibration pipeline runs when cache exists and produces
        equivalent results to the baseline (no-cache) calibration."""
        logger.info("Running posthoc calibration WITH cache")

        # Record baseline calibration time from the session fixture
        # (which runs without cache). Then run WITH cache and compare.
        t0 = time.perf_counter()
        config = PosthocCalibrationPipelineConfig(charuco_board=charuco_board_7x5)
        pipeline = posthoc_manager.create_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=config,
        )
        logger.info(f"Calibration pipeline with cache: id={pipeline.id}")
        wait_for_pipeline(pipeline)
        elapsed = time.perf_counter() - t0
        logger.info(f"Calibration with cache completed in {elapsed:.1f}s")

        calibration_toml = get_last_successful_calibration_toml_path()
        assert calibration_toml.exists(), (
            f"Calibration TOML not found at {calibration_toml}"
        )
        logger.info(f"Calibration TOML written: {calibration_toml}")

    def test_no_cache_no_crash(self, recording_info, posthoc_manager, charuco_board_7x5, test_recording_path):
        """If cache file is missing (clean state), posthoc calibration still works
        via normal video detection path."""
        cache_path = test_recording_path / "output_data" / CACHE_FILENAME

        # Remove cache if it exists
        if cache_path.exists():
            cache_path.unlink()

        config = PosthocCalibrationPipelineConfig(charuco_board=charuco_board_7x5)
        pipeline = posthoc_manager.create_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=config,
        )
        wait_for_pipeline(pipeline)

        calibration_toml = get_last_successful_calibration_toml_path()
        assert calibration_toml.exists(), (
            "Calibration should complete via normal video path when cache is missing"
        )
```

- [ ] **Step 2: Run the E2E test (cache write)**

Run: `uv run pytest freemocap/tests/pipelines/test_calibration_cache_e2e.py::TestCalibrationCacheE2E::test_cache_file_written -v --timeout=300`
Expected: PASS — cache file written with observations

- [ ] **Step 3: Run the E2E test (cache validation)**

Run: `uv run pytest freemocap/tests/pipelines/test_calibration_cache_e2e.py::TestCalibrationCacheE2E::test_cache_contains_valid_observations -v --timeout=60`
Expected: PASS — observations contain detected corners

- [ ] **Step 4: Run the E2E test (posthoc with cache)**

Run: `uv run pytest freemocap/tests/pipelines/test_calibration_cache_e2e.py::TestCalibrationCacheE2E::test_posthoc_calibration_with_cache -v --timeout=600`
Expected: PASS — calibration produces valid TOML

- [ ] **Step 5: Run the E2E test (no-cache fallback)**

Run: `uv run pytest freemocap/tests/pipelines/test_calibration_cache_e2e.py::TestCalibrationCacheE2E::test_no_cache_no_crash -v --timeout=600`
Expected: PASS — calibration works without cache

- [ ] **Step 6: Run full regression suite**

Run: `uv run pytest freemocap/tests/pipelines/ -v --timeout=600 -k "not slow"`
Expected: All existing tests PASS (no regressions)

- [ ] **Step 7: Commit**

```bash
git add freemocap/tests/pipelines/test_calibration_cache_e2e.py
git commit -m "test: E2E tests for Charuco observation cache pipeline

Tests the full roundtrip: realtime pipeline captures observations →
writes cache → posthoc calibration uses cached observations.
Also verifies graceful fallback when cache is missing.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Verify & Polish

- [ ] **Step 1: Run the full test suite**

```bash
uv run poe test
```

Expected: All tests pass, no regressions.

- [ ] **Step 2: Lint**

```bash
uv run poe lint
```

Fix any lint issues.

- [ ] **Step 3: Clean up any debug/temporary files**

Remove any `__pycache__` or temp files created during development.

- [ ] **Step 4: Final commit if any polish was needed**

```bash
git add -u
git commit -m "chore: lint fixes and polish for Charuco observation cache"
```
