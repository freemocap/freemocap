"""Resource-request parity before migrating Core's factory to SkellyTracker."""

from unittest.mock import patch

import pytest
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoDetectorConfig
from skellytracker.core.sessions.cpu_session import CpuSession
from skellytracker.core.sessions.mediapipe_session import MediaPipeSession
from skellytracker.core.sessions.onnx_session import OnnxSession
from skellytracker.core.tracker import tracker_session_requests as tracker_requests

from freemocap.core.tracking.tracker_factory import (
    build_mediapipe_tracker_config,
    skeleton_tracker_config,
    tracker_session_requests as core_requests,
)


@pytest.mark.parametrize('tracker_kind', ['rtmw', 'mediapipe', 'charuco', 'combined'])
@pytest.mark.parametrize('batch_size', [1, 3])
@pytest.mark.parametrize('provider', [None, 'cpu', 'cuda'])
@pytest.mark.parametrize('disable_gpu', [None, True])
def test_existing_core_requests_match_registry_factory(tracker_kind, batch_size, provider, disable_gpu):
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
        expected = core_requests(config=tracker_config, batch_size=batch_size, execution_provider=provider,
                                 mediapipe_disable_gpu=disable_gpu)
        actual = tracker_requests(tracker_config, batch_size=batch_size,
                                  onnx_overrides={'execution_provider': provider},
                                  mediapipe_overrides={'disable_gpu': disable_gpu})
        assert actual == expected
        onnx_create.assert_not_called()
        mediapipe_create.assert_not_called()
        cpu_create.assert_not_called()
