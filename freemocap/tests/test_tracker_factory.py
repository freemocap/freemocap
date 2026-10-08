"""Resolved detector configuration and resource ownership at construction."""

from unittest.mock import MagicMock, patch

import pytest
from skellytracker.core import DetectionStageConfig, Tracker, TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.charuco import (
    CharucoDetectorConfig,
)

from freemocap.core.tracking.tracker_factory import build_configured_tracker


def test_wrist_crops_request_both_cpu_and_mediapipe_backends() -> None:
    from freemocap.core.tracking.tracker_factory import (
        build_mediapipe_tracker_config, tracker_session_requests,
    )
    config = build_mediapipe_tracker_config()
    body = config.stages[0]
    assert [child.name for child in body.children] == ["right_hand", "left_hand", "face"]
    for child, side in zip(body.children[:2], ("right", "left")):
        assert child.object_detector.center_keypoint_names == (f"{side}_index", f"{side}_pinky")
        assert child.keypoint_detectors[0].assumed_handedness == side
        assert child.keypoint_detectors[0].num_hands == 1
    requests = tracker_session_requests(config=config, batch_size=3, execution_provider=None)
    assert {request.config.backend for request in requests} == {"cpu", "mediapipe"}


def test_direct_onnx_creation_is_serialized_across_factory_paths() -> None:
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import time
    from freemocap.core.tracking.tracker_factory import (
        OnnxSession, build_skeleton_onnx_session, skeleton_tracker_config,
    )
    active = peak = 0
    counter_lock = threading.Lock()
    start = threading.Barrier(2)

    def create_session(config):
        nonlocal active, peak
        with counter_lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.05)
            return OnnxSession()
        finally:
            with counter_lock:
                active -= 1

    def build(configured):
        start.wait(timeout=5)
        if configured:
            config = skeleton_tracker_config(model_name="rtmw-x-l_256x192", confidence_threshold=0.4,
                                             video_fps=30.0, keypoint_bbox_expansion=0.05)
            return build_configured_tracker(config=config, batch_size=1)
        return build_skeleton_onnx_session(batch_size=1)

    with patch("freemocap.core.tracking.tracker_factory.OnnxSession.create", side_effect=create_session), \
         patch("freemocap.core.tracking.tracker_factory.Tracker.create", return_value=Tracker(stages=[])), \
         ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(build, [False, True]))
    assert len(results) == 2
    assert peak == 1


def test_hand_merge_preserves_order_missing_points_and_other_children() -> None:
    import numpy as np
    from skellytracker.core.data_primitives.keypoints import Keypoints
    from skellytracker.core.data_primitives.observation import Observation, StageObservation
    from freemocap.core.tracking.tracker_factory import merge_mediapipe_hand_face_children

    def points(name, value):
        return Keypoints(names=(name,), xyz=np.full((1, 3), value, dtype=float),
                         visibility=np.array([0.0 if np.isnan(value) else 1.0]))

    board = StageObservation(name="board", keypoints=points("corner", 5))
    body = StageObservation(name="body", keypoints=points("nose", 1), children={
        "face": StageObservation(name="face", keypoints=points("face_0", 4)),
        "left_hand": StageObservation(name="left_hand", keypoints=points("left_hand_wrist", np.nan)),
        "right_hand": StageObservation(name="right_hand", keypoints=points("right_hand_wrist", 2)),
        "board": board,
    })
    observation = Observation(frame_number=2, image_size=(100, 100), stages={"body": body})
    merge_mediapipe_hand_face_children(observation)
    merge_mediapipe_hand_face_children(observation)
    assert body.keypoints.names == ("nose", "right_hand_wrist", "left_hand_wrist", "face_0")
    np.testing.assert_allclose(body.keypoints.xyz[:, 0], [1, 2, np.nan, 4], equal_nan=True)
    assert body.keypoints.visibility[2] == 0
    assert body.children == {"board": board}


@pytest.mark.parametrize("fail", [False, True])
def test_configured_tracker_preserves_nested_config_and_cleans_up(fail: bool) -> None:
    config = TrackerConfig(
        stages=[
            DetectionStageConfig(
                name="parent",
                children=[
                    DetectionStageConfig(
                        name="board", keypoint_detectors=[CharucoDetectorConfig()]
                    )
                ],
            )
        ]
    )
    session = MagicMock()
    with (
        patch(
            "freemocap.core.tracking.tracker_factory.CpuSession.create",
            return_value=session,
        ),
        patch(
            "freemocap.core.tracking.tracker_factory.Tracker.create",
            return_value=Tracker(stages=[]),
        ) as create,
    ):
        if fail:
            create.side_effect = RuntimeError("detector construction failed")
            with pytest.raises(RuntimeError, match="detector construction failed"):
                build_configured_tracker(config=config, batch_size=1)
            session.close.assert_called_once_with()
        else:
            tracker = build_configured_tracker(config=config, batch_size=1)
            assert tracker is create.return_value
            session.close.assert_not_called()
        create.assert_called_once_with(config=config, sessions={"cpu": session})


def test_configured_tracker_rejects_invalid_batch_before_allocation() -> None:
    with pytest.raises(ValueError, match="batch_size must be positive"):
        build_configured_tracker(config=TrackerConfig(stages=[]), batch_size=0)
