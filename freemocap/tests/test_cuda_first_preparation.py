"""Exercise real scheduling/pooling with fake native construction only."""

import multiprocessing
from threading import Event
from time import monotonic
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


@pytest.mark.parametrize("failure", [False, True])
def test_first_cuda_result_and_later_frames_do_not_wait_for_preparation(failure):
    entered, release = Event(), Event()
    current = OnnxSession(execution_provider="cuda")
    candidate = OnnxSession(execution_provider="trt")
    retired = Mock(spec=OnnxSession)
    created = []
    jobs = []

    def create(config):
        created.append(config.execution_provider)
        return current

    def prepare(ticket):
        def build():
            entered.set()
            assert release.wait(5)
            if failure:
                raise RuntimeError("native build failed")
            return candidate
        job = OnnxPreparationJob(ticket=ticket, build=build, validate=lambda _: None)
        jobs.append(job)
        return job

    def adopt(candidate):
        current.execution_provider = candidate.execution_provider
        return retired

    registry = WorkerRegistry(global_kill_flag=multiprocessing.Value("b", False), worker_mode=WorkerMode.THREAD)
    with patch.object(OnnxSession, "create", side_effect=create), patch.object(
        OnnxSession, "preparation_job", side_effect=prepare,
    ), patch.object(OnnxSession, "adopt_prepared_backend", side_effect=adopt), patch(
        "freemocap.core.tracking.execution_providers.advertised_providers", return_value=["cuda", "trt"],
    ), patch("freemocap.core.tracking.execution_providers.inspect_tracker_providers",
             side_effect=lambda *_: (ModelProviderStatus("pose", None, (current.execution_provider,)),)):
        service = InferenceService(worker_registry=registry)
        service.start()
        try:
            client = service.register(InferenceRegistration(
                pipeline_id="live", mode=InferenceMode.REALTIME, tracker_config=TrackerConfig(stages=[]),
                sessions=(SessionRequest(session_type=OnnxSession, config=OnnxSessionConfig(batch_size=1)),),
                shutdown_flag=multiprocessing.Value("b", False),
            ))
            def submit(frame):
                return client.submit(InferenceRequest(frame_number=frame, images={"camera": np.zeros((8, 8, 3), dtype=np.uint8)})).result(timeout=2)
            assert submit(0)["camera"].frame_number == 0
            assert entered.wait(2)
            tracker = client._lease.tracker
            assert created == ["cuda"]
            assert submit(1)["camera"].frame_number == 1
            assert current.execution_provider == "cuda"
            release.set()
            deadline = monotonic() + 3
            while jobs[0].snapshot().phase not in (PreparationPhase.READY, PreparationPhase.FAILED):
                assert monotonic() < deadline
                Event().wait(0.005)
            previous_states = client._states
            with patch.object(tracker, "process_batch", wraps=tracker.process_batch) as process:
                assert submit(2)["camera"].frame_number == 2
                assert process.call_args.kwargs["states"] is previous_states
            assert client._lease.tracker is tracker
            assert current.execution_provider == ("cuda" if failure else "trt")
            status = service.provider_status()[0]
            assert status["preparation"]["phase"] == "failed" if failure else status["preparation"] == "activated"
        finally:
            release.set()
            service.close()
    if not failure:
        retired.close.assert_called_once()


def test_explicit_cuda_never_schedules_preparation():
    registry = WorkerRegistry(global_kill_flag=multiprocessing.Value("b", False), worker_mode=WorkerMode.THREAD)
    with patch.object(OnnxSession, "create", return_value=OnnxSession(execution_provider="cuda")), patch.object(
        OnnxSession, "preparation_job",
    ) as prepare, patch("freemocap.core.tracking.execution_providers.inspect_tracker_providers", return_value=()):
        service = InferenceService(worker_registry=registry)
        service.start()
        try:
            client = service.register(InferenceRegistration(
                pipeline_id="pinned", mode=InferenceMode.REALTIME, tracker_config=TrackerConfig(stages=[]),
                sessions=(SessionRequest(session_type=OnnxSession, config=OnnxSessionConfig(batch_size=1, execution_provider="cuda")),),
                shutdown_flag=multiprocessing.Value("b", False),
            ))
            for frame in range(2):
                client.submit(InferenceRequest(frame_number=frame, images={"camera": np.zeros((8, 8, 3), dtype=np.uint8)})).result(timeout=2)
            prepare.assert_not_called()
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
