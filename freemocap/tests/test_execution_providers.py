"""Requested provider propagation, observed providers and failure ownership."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from freemocap.core.tracking.execution_providers import (
    PROVIDER_NAMES, advertised_providers, inspect_onnx_session, inspect_tracker_providers,
)
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.pipeline.realtime import realtime_pipeline as live
from skellytracker.core.sessions.session_errors import SessionCreationError


@pytest.mark.parametrize('provider,native', PROVIDER_NAMES.items())
def test_explicit_provider_and_actual_session_report(provider, native, caplog):
    config = SimpleNamespace(execution_provider=provider, models=[SimpleNamespace(name='pose')])
    session = Mock()
    session.get_session.return_value.get_providers.return_value = [native, 'CPUExecutionProvider']
    with caplog.at_level('INFO'):
        report = inspect_onnx_session(session, config)
    assert report[0].requested_provider == provider
    assert report[0].applied_providers == (native, 'CPUExecutionProvider')
    assert 'applied_providers=' in caplog.text


def test_automatic_fallback_is_reported_but_explicit_fallback_is_rejected():
    session = Mock()
    session.get_session.return_value.get_providers.return_value = ['CPUExecutionProvider']
    config = SimpleNamespace(execution_provider=None, models=[SimpleNamespace(name='pose')])
    assert inspect_onnx_session(session, config)[0].requested_provider is None
    config.execution_provider = 'cuda'
    with pytest.raises(SessionCreationError, match='did not load'):
        inspect_onnx_session(session, config)


def test_borrowed_nested_session_is_inspected_without_closing_it():
    session = Mock(kind='onnx')
    session.get_session.return_value.get_providers.return_value = ['CPUExecutionProvider']
    child = SimpleNamespace(children=[], object_detector=None, keypoint_detectors=[SimpleNamespace(session=session)])
    tracker = SimpleNamespace(stages=[SimpleNamespace(children=[child], object_detector=None, keypoint_detectors=[])])
    request = SimpleNamespace(config=SimpleNamespace(backend='onnx', execution_provider='cpu', models=[SimpleNamespace(name='pose')]))
    assert inspect_tracker_providers(tracker, [request])[0].model_name == 'pose'
    session.close.assert_not_called()


@pytest.mark.parametrize('provider', [None, *PROVIDER_NAMES])
def test_posthoc_api_accepts_all_providers_for_both_implementations(provider):
    for implementation in ('typed_dataflow',):
        config = PosthocMocapPipelineConfig(executionProvider=provider, pipelineImplementation=implementation)
        assert config.execution_provider == provider
        assert config.model_dump(by_alias=True)['executionProvider'] == provider


def test_conflicting_saved_graph_provider_is_rejected():
    with pytest.raises(ValidationError, match='disagree'):
        PosthocMocapPipelineConfig(executionProvider='cpu', graphExecutionProvider='cuda')
    with pytest.raises(ValidationError):
        PosthocMocapPipelineConfig(executionProvider='not-a-provider')


def test_provider_route_lists_advertised_build_support_without_loading_models():
    from freemocap.api.http.onnx.onnx_router import onnx_router
    app = FastAPI()
    app.include_router(onnx_router, prefix='/freemocap')
    with patch('onnxruntime.get_available_providers', return_value=['CPUExecutionProvider']), \
         patch('onnxruntime.InferenceSession') as construct:
        response = TestClient(app).get('/freemocap/onnx/execution_providers')
    assert response.status_code == 200
    assert response.json() == {'available': ['cpu']}
    construct.assert_not_called()


def test_coreml_is_not_advertised_on_windows():
    with patch('onnxruntime.get_available_providers', return_value=['CoreMLExecutionProvider', 'CPUExecutionProvider']), \
         patch('freemocap.core.tracking.execution_providers.sys.platform', 'win32'):
        assert advertised_providers() == ['cpu']


@pytest.mark.parametrize('change', ['provider', 'model', 'filter'])
def test_live_changes_rebuild_only_affected_inference(change):
    pipeline = object.__new__(live.RealtimePipeline)
    pipeline.config = live.RealtimePipelineConfig()
    pipeline.config.camera_node_config.skeleton_tracking_enabled = True
    pipeline._calibration_update_pending = False
    pipeline.skeleton_inference_node = Mock(is_alive=True)
    original = pipeline.skeleton_inference_node
    pipeline.camera_group = Mock()
    pipeline.camera_group.id = 'cameras'
    pipeline.camera_nodes = {'camera': Mock()}
    pipeline.worker_registry = Mock()
    pipeline.inference_service = Mock()
    pipeline.ipc = Mock()
    pipeline.pubsub = Mock()
    updated = pipeline.config.model_copy(deep=True)
    if change == 'provider':
        updated.skeleton_inference_node_config.execution_provider = 'cpu'
    elif change == 'model':
        updated.camera_node_config.rtmpose_model_name = 'rtmw-l-m_256x192'
    else:
        updated.aggregator_config.realtime_filter_config = updated.aggregator_config.realtime_filter_config.model_copy(update={'gap_duration_s': .6})
    with patch.object(live.RealtimeSkeletonInferenceNode, 'create') as create:
        pipeline.update_config(updated)
    if change == 'filter':
        original.shutdown.assert_not_called()
        create.assert_not_called()
    else:
        original.shutdown.assert_called_once()
        create.assert_called_once()
        create.return_value.start.assert_called_once()
    pipeline.camera_group.close.assert_not_called()
    pipeline.inference_service.close.assert_not_called()


def test_per_camera_factory_receives_selected_provider():
    from freemocap.core.pipeline.realtime.camera_node import _build_skeleton_tracker_from_config
    from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
    from freemocap.core.tracking import tracker_factory
    with patch.object(tracker_factory, 'build_configured_tracker') as create:
        _build_skeleton_tracker_from_config(CameraNodeConfig(), 'cpu')
    assert create.call_args.kwargs['execution_provider'] == 'cpu'


def test_failed_explicit_direct_session_is_closed():
    from freemocap.core.tracking.tracker_factory import build_skeleton_onnx_session, OnnxSession
    session = OnnxSession()
    with patch.object(OnnxSession, 'create', return_value=session), \
         patch.object(OnnxSession, 'close') as close, \
         patch.object(OnnxSession, 'get_session') as native:
        native.return_value.get_providers.return_value = ['CPUExecutionProvider']
        with pytest.raises(SessionCreationError):
            build_skeleton_onnx_session(batch_size=1, execution_provider='cuda')
    close.assert_called_once()


@pytest.mark.parametrize('provider', list(PROVIDER_NAMES))
def test_graph_receives_each_explicit_provider(provider):
    from freemocap.core.pipeline.dataflow.application_pipeline import resolve_tracking_provider
    assert resolve_tracking_provider(PosthocMocapPipelineConfig(executionProvider=provider)) == provider


def test_graph_auto_policy_and_mediapipe_ignore_hidden_onnx_selection():
    from freemocap.core.pipeline.dataflow.application_pipeline import resolve_tracking_provider
    with patch('onnxruntime.get_available_providers', return_value=['CPUExecutionProvider']):
        assert resolve_tracking_provider(PosthocMocapPipelineConfig()) == 'cpu'
    with patch('onnxruntime.get_available_providers', return_value=['CUDAExecutionProvider', 'CPUExecutionProvider']):
        assert resolve_tracking_provider(PosthocMocapPipelineConfig()) == 'cuda'
    assert resolve_tracking_provider(PosthocMocapPipelineConfig(detectorType='mediapipe', executionProvider='cuda')) == 'cpu'


def test_per_camera_startup_failure_closes_initialized_resources():
    import multiprocessing
    from multiprocessing.queues import Queue
    from freemocap.core.pipeline.realtime import camera_node as camera
    memory = Mock(spec=camera.CameraSharedMemoryRingBuffer)
    board = Mock()
    ipc = Mock(spec=camera.PipelineIPC)
    config = camera.CameraNodeConfig(charuco_tracking_enabled=True, skeleton_tracking_enabled=True)
    with patch.object(camera.CameraSharedMemoryRingBuffer, 'recreate', return_value=memory), \
         patch.object(camera, '_build_charuco_tracker_from_config', return_value=(board, None)), \
         patch.object(camera, '_build_skeleton_tracker_from_config', side_effect=RuntimeError('provider failed')):
        with pytest.raises(RuntimeError, match='provider failed'):
            camera.CameraNode._run(camera_id='camera', config=config, ipc=ipc,
                camera_shm_dto=Mock(spec=camera.SharedMemoryRingBufferDTO),
                shutdown_self_flag=multiprocessing.Value('b', False),
                process_frame_number_sub=Mock(spec=Queue), pipeline_config_sub=Mock(spec=Queue),
                camera_output_pub=Mock(spec=Queue), timing_pub=Mock(spec=Queue), execution_provider='cuda')
    board.close.assert_called_once()
    memory.close.assert_called_once()
    ipc.shutdown_pipeline.assert_called_once()


def test_session_status_endpoint_reports_actual_values():
    from freemocap.api.http.onnx.onnx_router import onnx_router
    app = FastAPI()
    app.include_router(onnx_router, prefix='/freemocap')
    service = Mock()
    service.provider_status.return_value = [{'pipeline_id': 'live', 'mode': 'realtime', 'models': [
        {'model_name': 'pose', 'requested_provider': None, 'applied_providers': ('CUDAExecutionProvider', 'CPUExecutionProvider')}]}]
    with patch('freemocap.app.freemocap_application.get_freemocap_app', return_value=SimpleNamespace(inference_service=service)):
        response = TestClient(app).get('/freemocap/onnx/session_providers')
    assert response.status_code == 200
    model = response.json()[0]['models'][0]
    assert model['requested_provider'] is None
    assert model['applied_providers'] == ['CUDAExecutionProvider', 'CPUExecutionProvider']


def test_graph_auto_uses_available_coreml_instead_of_forcing_cpu():
    from freemocap.core.pipeline.dataflow.application_pipeline import resolve_tracking_provider
    with patch('onnxruntime.get_available_providers', return_value=['CoreMLExecutionProvider', 'CPUExecutionProvider']), \
         patch('skellytracker.core.sessions.ort_session_utils.sys.platform', 'darwin'):
        assert resolve_tracking_provider(PosthocMocapPipelineConfig()) == 'coreml'


def test_graph_auto_preserves_cuda_preference_over_tensorrt_compilation():
    from freemocap.core.pipeline.dataflow.application_pipeline import resolve_tracking_provider
    with patch('onnxruntime.get_available_providers',
               return_value=['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']):
        assert resolve_tracking_provider(PosthocMocapPipelineConfig()) == 'cuda'
