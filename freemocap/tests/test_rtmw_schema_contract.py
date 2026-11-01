"""Core uses the emitted RTMW schema without changing saved application identities."""

from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest
import skellytracker
import yaml
from skellytracker.core.detectors.keypoint_detectors.rtmw.wholebody.rtmw_wholebody_detector import (
    RTMWWholebodyDetectorConfig, RTMW_WHOLEBODY_MODEL_SPECS,
)
from skellytracker.core.sessions.onnx_session import OnnxSession

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.mocap.tracker_mappings import tracker_keypoint_names
from freemocap.core.tracking.tracker_definitions import RTMPOSE_WHOLEBODY_DEFINITION
from freemocap.core.tracking.tracker_factory import build_skeleton_onnx_session, skeleton_tracker_config


def test_published_schema_preserves_recording_names_landmarks_and_edges():
    # The prior emitted schema is an independent compatibility oracle for the
    # consumer. Production Core no longer knows this package-internal path.
    schema_path = (Path(skellytracker.__file__).parent / 'core/detectors/keypoint_detectors'
                   / 'rtmpose/wholebody/rtmpose_wholebody.yaml')
    original_schema = yaml.safe_load(schema_path.read_text(encoding='utf-8'))
    definition = RTMPOSE_WHOLEBODY_DEFINITION
    assert definition.name == 'rtmpose_wholebody'
    assert definition.tracked_points == tuple(original_schema['tracked_points'])
    assert definition.connections == tuple(tuple(edge) for edge in original_schema['connections'])
    assert tracker_keypoint_names('rtmpose') == tuple(sorted(definition.tracked_points))


@pytest.mark.parametrize('model_name', tuple(RTMW_WHOLEBODY_MODEL_SPECS))
@pytest.mark.parametrize('confidence_threshold', [0.4, 0.65])
def test_live_and_posthoc_configs_preserve_model_and_confidence(model_name, confidence_threshold):
    realtime_config = skeleton_tracker_config(model_name=model_name,
        confidence_threshold=confidence_threshold, video_fps=30., keypoint_bbox_expansion=.05)
    posthoc_config = PosthocMocapPipelineConfig(rtmpose_model_name=model_name,
        rtmpose_confidence_threshold=confidence_threshold).tracker_config
    for tracker_config in (realtime_config, posthoc_config):
        detector_config = tracker_config.stages[0].keypoint_detectors[0]
        assert type(detector_config) is RTMWWholebodyDetectorConfig
        assert detector_config.model_name == model_name
        assert detector_config.confidence_threshold == confidence_threshold
        assert detector_config.model_dump()['detector_type'] == 'rtmpose'
        assert tracker_config.stages[0].name == 'body'
        assert tracker_config.stages[0].bbox_policy.fitness_checks == []


def test_camera_defaults_preserve_detector_configuration():
    node_config = CameraNodeConfig()
    detector_config = node_config.skeleton_tracker_config.stages[0].keypoint_detectors[0]
    assert type(detector_config) is RTMWWholebodyDetectorConfig
    assert node_config.detector_type == detector_config.detector_type == 'rtmpose'
    assert detector_config.model_name == node_config.rtmpose_model_name == 'rtmw-x-l_256x192'
    assert detector_config.confidence_threshold == node_config.rtmpose_confidence_threshold == 0.4


@pytest.mark.parametrize('model_name', tuple(RTMW_WHOLEBODY_MODEL_SPECS))
def test_direct_session_preserves_models_and_provider_settings(model_name):
    with patch('freemocap.core.tracking.tracker_factory.OnnxSession.create',
               return_value=OnnxSession()) as session_create, \
         patch.object(OnnxSession, 'get_session') as get_session:
        get_session.return_value.get_providers.return_value = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        session = build_skeleton_onnx_session(batch_size=3, execution_provider='cuda',
                                             device_id=1, model_name=model_name, yolox_model_name='yolox-tiny')
    session_config = session_create.call_args.args[0]
    assert session is session_create.return_value
    assert [model.name for model in session_config.models] == ['yolox-tiny', model_name]
    assert session_config.batch_size == 3
    assert session_config.execution_provider == 'cuda'
    assert session_config.device_id == 1


def test_schema_imports_do_not_load_native_inference_libraries():
    result = subprocess.run([sys.executable, '-B', '-c',
        'import sys; '
        'import freemocap.core.tracking.tracker_definitions; '
        'import freemocap.core.tasks.mocap.tracker_mappings; '
        'assert "onnxruntime" not in sys.modules; assert "mediapipe" not in sys.modules'],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
