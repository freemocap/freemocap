"""Exercise real scheduling/pooling with fake native construction only."""

import multiprocessing
from threading import Event
from unittest.mock import Mock, patch

import numpy as np
import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core.config.tracker_config import TrackerConfig
from skellytracker.core.sessions.onnx_model_spec import OnnxSessionConfig
from skellytracker.core.sessions.onnx_preparation import OnnxPreparationJob, OnnxPreparationTicket, PreparationPhase
from skellytracker.core.sessions.onnx_session import OnnxSession
from skellytracker.core.sessions.shared_sessions import SessionRequest

from freemocap.core.pipeline.inference_service import (
    InferenceMode, InferenceRegistration, InferenceRequest, InferenceService,
)
from freemocap.core.tracking.execution_providers import ModelProviderStatus


@pytest.mark.parametrize("trt_available", [False, True])
@pytest.mark.parametrize("camera_count", [1, 4])
def test_auto_stays_on_cuda_without_creating_preparation(trt_available, camera_count):
    current = OnnxSession(execution_provider="cuda")
    created = []

    def create(config, *, progress=None):
        created.append((config.execution_provider, config.batch_size))
        return current

    registry = WorkerRegistry(global_kill_flag=multiprocessing.Value("b", False), worker_mode=WorkerMode.THREAD)
    with patch.object(OnnxSession, "create", side_effect=create), patch.object(
        OnnxSession, "preparation_job", side_effect=AssertionError("Auto must not prepare TensorRT"),
    ) as prepare, patch(
        "freemocap.core.tracking.execution_providers.advertised_providers",
        return_value=["cuda", "trt"] if trt_available else ["cuda"],
    ), patch("freemocap.core.tracking.execution_providers.inspect_tracker_providers",
             return_value=(ModelProviderStatus("pose", None, ("CUDAExecutionProvider",)),)):
        service = InferenceService(worker_registry=registry)
        service.start()
        try:
            client = service.register(InferenceRegistration(
                pipeline_id="live", mode=InferenceMode.REALTIME, tracker_config=TrackerConfig(stages=[]),
                sessions=(SessionRequest(session_type=OnnxSession, config=OnnxSessionConfig(batch_size=camera_count)),),
                shutdown_flag=multiprocessing.Value("b", False),
            ))
            with patch.object(service._preparation, "submit", side_effect=AssertionError("Auto queued native work")) as submit_job:
                for frame in range(3):
                    result = client.submit(InferenceRequest(frame_number=frame, images={
                        str(camera): np.zeros((8, 8, 3), dtype=np.uint8) for camera in range(camera_count)
                    })).result(timeout=2)
                    assert all(item.frame_number == frame for item in result.values())
                assert created == [("cuda", camera_count)]
                prepare.assert_not_called()
                submit_job.assert_not_called()
                assert client._preparation_job is None
                assert service.provider_status()[0]["preparation"] == (
                    "Using CUDA; automatic TensorRT preparation is disabled" if trt_available else
                    "Using CUDA; TensorRT provider is unavailable")
        finally:
            service.close()


@pytest.mark.parametrize("provider", ["cuda", "trt"])
def test_explicit_provider_request_never_triggers_automatic_preparation(provider):
    registry = WorkerRegistry(global_kill_flag=multiprocessing.Value("b", False), worker_mode=WorkerMode.THREAD)
    with patch.object(OnnxSession, "create", side_effect=lambda config, **kwargs: OnnxSession(execution_provider=config.execution_provider)) as create, patch.object(
        OnnxSession, "preparation_job",
    ) as prepare, patch("freemocap.core.tracking.execution_providers.advertised_providers", return_value=["cuda", "trt"]), patch("freemocap.core.tracking.execution_providers.inspect_tracker_providers", return_value=()):
        service = InferenceService(worker_registry=registry)
        service.start()
        try:
            client = service.register(InferenceRegistration(
                pipeline_id="pinned", mode=InferenceMode.REALTIME, tracker_config=TrackerConfig(stages=[]),
                sessions=(SessionRequest(session_type=OnnxSession, config=OnnxSessionConfig(batch_size=1, execution_provider=provider)),),
                shutdown_flag=multiprocessing.Value("b", False),
            ))
            for frame in range(2):
                client.submit(InferenceRequest(frame_number=frame, images={"camera": np.zeros((8, 8, 3), dtype=np.uint8)})).result(timeout=2)
            prepare.assert_not_called()
            assert create.call_args.args[0].execution_provider == "cuda"
            assert service.preparation_status("pinned")["requested_provider"] == provider
        finally:
            service.close()


def test_shutdown_reports_native_work_still_running_and_drains_after_release():
    from freemocap.core.pipeline.inference_preparation import InferencePreparation
    registry = WorkerRegistry(global_kill_flag=multiprocessing.Value("b", False), worker_mode=WorkerMode.THREAD)
    worker = InferencePreparation(registry)
    entered, release = Event(), Event()
    backend = Mock(spec=OnnxSession)

    def build():
        entered.set()
        assert release.wait(5)
        return backend

    job = OnnxPreparationJob(ticket=OnnxPreparationTicket("request", 0, "identity"), build=build, validate=lambda _: None)
    worker.start()
    try:
        worker.submit(job)
        assert entered.wait(2)
        with patch.object(worker.worker, "join"), pytest.raises(RuntimeError, match="still running"):
            worker.close()
        assert job.snapshot().phase == PreparationPhase.STOPPING
        backend.close.assert_not_called()
    finally:
        release.set()
        worker.close()
    backend.close.assert_called_once()
    assert job.snapshot().phase == PreparationPhase.CANCELLED
