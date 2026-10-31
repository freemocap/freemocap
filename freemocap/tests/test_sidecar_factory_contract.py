"""Core session requirements remain stable across the registry migration."""

from unittest.mock import patch

import pytest
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoDetectorConfig
from skellytracker.core.sessions.cpu_session import CpuSession, CpuSessionConfig
from skellytracker.core.sessions.mediapipe_session import MediaPipeSession, MediaPipeSessionConfig
from skellytracker.core.sessions.onnx_session import OnnxSession, OnnxSessionConfig
from skellytracker.core.sessions.shared_sessions import SessionRequest
from skellytracker.core.detectors.keypoint_detectors.rtmpose import (
    RTMPoseKeypointDetector, RTMPoseBodyDetectorConfig, RTMPoseBodyDetector,
    RTMPoseHandDetectorConfig, RTMPoseHandDetector, RTMPoseFaceDetectorConfig, RTMPoseFaceDetector,
)
from skellytracker.core.detectors.object_detectors.yolox import YoloxPersonDetector

from freemocap.core.tracking.tracker_factory import (
    build_mediapipe_tracker_config,
    skeleton_tracker_config,
    tracker_session_requests as core_requests,
)


@pytest.mark.parametrize('tracker_kind', ['rtmw', 'mediapipe', 'charuco', 'combined'])
@pytest.mark.parametrize('batch_size', [1, 3])
@pytest.mark.parametrize('provider', [None, 'cpu', 'cuda'])
@pytest.mark.parametrize('disable_gpu', [None, True])
def test_core_requests_preserve_declared_models_and_settings(tracker_kind, batch_size, provider, disable_gpu):
    rtmw_config = skeleton_tracker_config(model_name='rtmw-x-l_256x192', confidence_threshold=.4,
                                   video_fps=30., keypoint_bbox_expansion=.05)
    mediapipe_config = build_mediapipe_tracker_config()
    charuco_config = TrackerConfig(stages=[DetectionStageConfig(
        name='board', keypoint_detectors=[CharucoDetectorConfig()])])
    combined_config = rtmw_config.model_copy(deep=True)
    combined_config.stages[0].children.extend([*mediapipe_config.stages, *charuco_config.stages])
    tracker_config = {'rtmw': rtmw_config, 'mediapipe': mediapipe_config,
                      'charuco': charuco_config, 'combined': combined_config}[tracker_kind]
    with (patch.object(OnnxSession, 'create') as onnx_create,
          patch.object(MediaPipeSession, 'create') as mediapipe_create,
          patch.object(CpuSession, 'create') as cpu_create):
        expected_requests = []
        if tracker_kind in ('mediapipe', 'charuco', 'combined'):
            expected_requests.append(SessionRequest(CpuSession, CpuSessionConfig()))
        if tracker_kind in ('mediapipe', 'combined'):
            expected_requests.append(SessionRequest(MediaPipeSession,
                MediaPipeSessionConfig(disable_gpu=disable_gpu)))
        if tracker_kind in ('rtmw', 'combined'):
            expected_requests.append(SessionRequest(OnnxSession, OnnxSessionConfig(
                batch_size=batch_size, execution_provider=provider,
                models=[RTMPoseKeypointDetector.model_spec('rtmw-x-l_256x192'),
                        YoloxPersonDetector.model_spec('yolox-m')],
            )))
        actual_requests = core_requests(config=tracker_config, batch_size=batch_size,
                                        execution_provider=provider, mediapipe_disable_gpu=disable_gpu)
        assert actual_requests == tuple(expected_requests)
        onnx_create.assert_not_called()
        mediapipe_create.assert_not_called()
        cpu_create.assert_not_called()


@pytest.mark.parametrize('config_type,detector_type', [
    (RTMPoseBodyDetectorConfig, RTMPoseBodyDetector),
    (RTMPoseHandDetectorConfig, RTMPoseHandDetector),
    (RTMPoseFaceDetectorConfig, RTMPoseFaceDetector),
])
def test_registry_discovers_nested_models_without_core_type_checks(config_type, detector_type):
    detector_config = config_type()
    tracker_config = TrackerConfig(stages=[DetectionStageConfig(name='parent', children=[
        DetectionStageConfig(name='child', keypoint_detectors=[detector_config, detector_config]),
    ])])
    with patch.object(OnnxSession, 'create') as session_create:
        requests = core_requests(config=tracker_config, batch_size=3, execution_provider='cpu')
    assert len(requests) == 1
    assert requests[0].config.models == [detector_type.model_spec(detector_config.model_name)]
    assert requests[0].config.batch_size == 3
    assert requests[0].config.execution_provider == 'cpu'
    session_create.assert_not_called()


def test_empty_tracker_is_rejected_before_allocation():
    with patch.object(OnnxSession, 'create') as session_create:
        with pytest.raises(ValueError, match='at least one detector'):
            core_requests(config=TrackerConfig(stages=[]), batch_size=1, execution_provider=None)
    session_create.assert_not_called()
