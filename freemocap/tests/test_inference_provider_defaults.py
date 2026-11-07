"""Application defaults and saved TRT selections never construct TensorRT sessions."""
import multiprocessing
from unittest.mock import patch

import numpy as np
import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core.config.tracker_config import TrackerConfig
from skellytracker.core.sessions.onnx_model_spec import OnnxSessionConfig
from skellytracker.core.sessions.onnx_session import OnnxSession
from skellytracker.core.sessions.shared_sessions import SessionRequest

from freemocap.core.pipeline.inference_service import (
    InferenceMode, InferenceRegistration, InferenceRequest, InferenceService,
)

pytestmark = pytest.mark.usefixtures('simulated_providers_load')


@pytest.mark.parametrize('mode', [InferenceMode.REALTIME, InferenceMode.POSTHOC])
@pytest.mark.parametrize('requested', [None, 'trt'])
@pytest.mark.parametrize('camera_count', [1, 4])
def test_auto_and_saved_trt_use_cuda_and_only_the_inference_worker(mode, requested, camera_count):
    registry = WorkerRegistry(global_kill_flag=multiprocessing.Value('b', False), worker_mode=WorkerMode.THREAD)
    created = []

    def native_create(config, *, progress=None):
        assert config.execution_provider == 'cuda'
        created.append((config.execution_provider, config.batch_size))
        return OnnxSession(execution_provider='cuda')

    with patch.object(registry, 'create_worker', wraps=registry.create_worker) as workers, \
         patch.object(OnnxSession, 'create', side_effect=native_create), \
         patch('freemocap.core.tracking.execution_providers.advertised_providers', return_value=['trt', 'cuda', 'cpu']), \
         patch('freemocap.core.tracking.execution_providers.inspect_tracker_providers', return_value=()):
        service = InferenceService(worker_registry=registry)
        service.start()
        try:
            client = service.register(InferenceRegistration(
                pipeline_id='live', mode=mode, tracker_config=TrackerConfig(stages=[]),
                sessions=(SessionRequest(session_type=OnnxSession,
                          config=OnnxSessionConfig(batch_size=camera_count, execution_provider=requested)),),
                shutdown_flag=multiprocessing.Value('b', False),
            ))
            for frame in range(4):
                result = client.submit(InferenceRequest(frame_number=frame, images={
                    str(camera): np.zeros((8, 8, 3), dtype=np.uint8) for camera in range(camera_count)
                })).result(timeout=2)
                assert all(observation.frame_number == frame for observation in result.values())
            assert created == [('cuda', camera_count)]
            workers.assert_called_once()
            assert workers.call_args.kwargs['name'] == 'SharedInference'
            assert service.has_result('live')
            assert service.startup_status('live')['status'] == 'ready'
            assert set(service.provider_status()[0]) == {'pipeline_id', 'mode', 'models'}
        finally:
            service.close()


@pytest.mark.parametrize('requested,available,expected', [
    (None, ['coreml', 'cpu'], 'coreml'), ('trt', ['cpu'], 'cpu'),
    (None, ['directml', 'cpu'], 'directml'),
    ('cpu', ['cuda', 'cpu'], 'cpu'), ('cuda', ['cpu'], 'cuda'),
    ('coreml', ['cpu'], 'coreml'), ('directml', ['cpu'], 'directml'),
])
def test_safe_fallback_preserves_explicit_non_trt_selection(requested, available, expected):
    registry = WorkerRegistry(global_kill_flag=multiprocessing.Value('b', False), worker_mode=WorkerMode.THREAD)
    with patch('freemocap.core.tracking.execution_providers.advertised_providers', return_value=available), \
         patch.object(OnnxSession, 'create', side_effect=lambda config, **kwargs: OnnxSession(
             execution_provider=config.execution_provider)) as create, \
         patch('freemocap.core.tracking.execution_providers.inspect_tracker_providers', return_value=()):
        service = InferenceService(worker_registry=registry)
        service.start()
        try:
            client = service.register(InferenceRegistration(
                pipeline_id='fallback', mode=InferenceMode.REALTIME, tracker_config=TrackerConfig(stages=[]),
                sessions=(SessionRequest(session_type=OnnxSession, config=OnnxSessionConfig(batch_size=1, execution_provider=requested)),),
                shutdown_flag=multiprocessing.Value('b', False),
            ))
            client.submit(InferenceRequest(frame_number=0, images={'camera': np.zeros((8, 8, 3), dtype=np.uint8)})).result(timeout=2)
            assert create.call_args.args[0].execution_provider == expected
            assert client.registration.sessions[0].config.execution_provider == requested
        finally:
            service.close()
