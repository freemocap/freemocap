"""CPU scheduler integration for explicit preparation, cancellation and retry."""

import multiprocessing
from threading import Event
from time import monotonic
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core.config.tracker_config import TrackerConfig
from skellytracker.core.sessions.onnx_model_spec import OnnxSessionConfig
from skellytracker.core.sessions.onnx_preparation import OnnxPreparationJob
from skellytracker.core.sessions.onnx_session import OnnxSession
from skellytracker.core.sessions.shared_sessions import SessionRequest, SharedSessionPool

from freemocap.core.pipeline.inference_service import (
    InferenceMode, InferenceRegistration, InferenceRequest, InferenceService,
)
from freemocap.core.tracking.execution_providers import ModelProviderStatus


def wait_for(predicate):
    deadline = monotonic() + 4
    while not predicate():
        assert monotonic() < deadline, "condition did not become true"
        Event().wait(0.005)


@pytest.fixture
def inference():
    attempts, created = [], []
    advertised = ["cuda", "trt", "cpu"]
    def create(config, *, progress=None):
        created.append(config.execution_provider)
        return OnnxSession(execution_provider=config.execution_provider)
    def prepare(ticket):
        attempt = SimpleNamespace(entered=Event(), release=Event(), fail=False, ticket=ticket)
        def build():
            attempt.entered.set()
            assert attempt.release.wait(5)
            if attempt.fail:
                raise RuntimeError("fixture compilation failure")
            return OnnxSession(execution_provider="trt")
        attempt.job = OnnxPreparationJob(ticket=ticket, build=build, validate=lambda _: None)
        attempts.append(attempt)
        return attempt.job
    def adopt(current, candidate):
        current.execution_provider = candidate.execution_provider
        return OnnxSession()
    def inspect(tracker, requests):
        provider = requests[0].config.execution_provider
        return (ModelProviderStatus("pose", provider, (provider,)),)
    registry = WorkerRegistry(global_kill_flag=multiprocessing.Value("b", False), worker_mode=WorkerMode.THREAD)
    with patch.object(OnnxSession, "create", side_effect=create), patch.object(
        OnnxSession, "isolated_preparation_job", side_effect=prepare,
    ), patch.object(OnnxSession, "adopt_prepared_backend", adopt), patch(
        "freemocap.core.tracking.execution_providers.advertised_providers", side_effect=lambda: list(advertised),
    ), patch("freemocap.core.tracking.execution_providers.inspect_tracker_providers", side_effect=inspect):
        service = InferenceService(worker_registry=registry)
        service.start()
        def register(name="live", provider=None):
            return service.register(InferenceRegistration(
                pipeline_id=name, mode=InferenceMode.REALTIME, tracker_config=TrackerConfig(stages=[]),
                sessions=(SessionRequest(session_type=OnnxSession, config=OnnxSessionConfig(batch_size=1, execution_provider=provider)),),
                shutdown_flag=multiprocessing.Value("b", False),
            ))
        try:
            yield SimpleNamespace(service=service, register=register, attempts=attempts, created=created, advertised=advertised)
        finally:
            for attempt in attempts:
                attempt.release.set()
            service.close()


def frame(client, ordinal):
    return client.submit(InferenceRequest(frame_number=ordinal, images={"camera": np.zeros((8, 8, 3), dtype=np.uint8)})).result(timeout=2)


def test_saved_trt_starts_cuda_and_requires_explicit_preparation(inference):
    client = inference.register(provider="trt")
    assert not inference.service.has_result("live")
    frame(client, 0)
    assert inference.service.has_result("live")
    status = inference.service.preparation_status("live")
    assert status["requested_provider"] == "trt" and status["active_provider"] == "cuda"
    assert status["status"] == "idle" and status["can_prepare"]
    assert inference.created == ["cuda"] and inference.attempts == []
    assert client.provider_status[0].requested_provider == "trt"
    assert client.provider_status[0].applied_providers == ("cuda",)


def test_explicit_request_runs_without_new_frame_and_keeps_other_clients_usable(inference):
    client = inference.register()
    pinned = inference.register("pinned", "cuda")
    frame(client, 0)
    frame(pinned, 0)
    assert inference.service.request_preparation("live")["status"] == "queued"
    wait_for(lambda: len(inference.attempts) == 1 and inference.attempts[0].entered.is_set())
    assert inference.service.preparation_status("live")["status"] == "running"
    assert frame(client, 1)["camera"].frame_number == 1
    assert frame(pinned, 1)["camera"].frame_number == 1
    with pytest.raises(ValueError):
        inference.service.request_preparation("pinned")
    inference.attempts[0].release.set()
    wait_for(lambda: inference.service.preparation_status("live")["status"] == "activated")
    assert inference.service.preparation_status("live")["active_provider"] == "trt"
    assert inference.service.preparation_status("pinned")["active_provider"] == "cuda"


def test_cancel_waits_for_cleanup_then_allows_fresh_generation_retry(inference):
    client = inference.register()
    frame(client, 0)
    inference.service.request_preparation("live")
    wait_for(lambda: len(inference.attempts) == 1 and inference.attempts[0].entered.is_set())
    inference.service.cancel_preparation("live")
    wait_for(lambda: inference.service.preparation_status("live")["status"] == "stopping")
    assert not inference.service.preparation_status("live")["can_prepare"]
    inference.attempts[0].release.set()
    wait_for(lambda: inference.service.preparation_status("live")["status"] == "cancelled")
    inference.service.request_preparation("live")
    wait_for(lambda: len(inference.attempts) == 2)
    assert inference.attempts[1].ticket.generation == inference.attempts[0].ticket.generation + 1
    inference.attempts[1].release.set()
    wait_for(lambda: inference.service.preparation_status("live")["status"] == "activated")


def test_failure_is_retryable_and_does_not_stop_cuda(inference):
    client = inference.register()
    frame(client, 0)
    inference.service.request_preparation("live")
    wait_for(lambda: len(inference.attempts) == 1)
    inference.attempts[0].fail = True
    inference.attempts[0].release.set()
    wait_for(lambda: inference.service.preparation_status("live")["status"] == "failed")
    status = inference.service.preparation_status("live")
    assert status["active_provider"] == "cuda" and status["can_prepare"]
    assert "fixture compilation failure" in status["error"]
    assert status["message"] == "TensorRT preparation failed; CUDA remains active"
    assert frame(client, 1)["camera"].frame_number == 1
    inference.service.request_preparation("live")
    wait_for(lambda: len(inference.attempts) == 2)
    inference.attempts[1].release.set()
    wait_for(lambda: inference.service.preparation_status("live")["status"] == "activated")


def test_cancel_before_owner_consumes_intent_never_builds(inference):
    client = inference.register()
    frame(client, 0)
    with inference.service._condition:
        inference.service.request_preparation("live")
        inference.service.cancel_preparation("live")
    wait_for(lambda: inference.service.preparation_status("live")["status"] == "cancelled")
    assert inference.attempts == []


@pytest.mark.parametrize("requested", [None, "trt"])
def test_realtime_never_falls_through_to_trt_without_cuda(inference, requested):
    inference.advertised[:] = ["trt", "cpu"]
    client = inference.register(provider=requested)
    frame(client, 0)
    assert inference.created == ["cpu"]
    assert inference.service.preparation_status("live")["status"] == "unavailable"
    assert inference.attempts == []


def test_unknown_pipeline_rejects_preparation_controls(inference):
    for method in (inference.service.preparation_status, inference.service.request_preparation,
                   inference.service.cancel_preparation):
        with pytest.raises(ValueError, match="No running pipeline"):
            method("unknown")


def test_shared_clients_and_late_join_report_actual_trt_provider(inference):
    first = inference.register()
    shared = inference.register("shared")
    frame(first, 0)
    frame(shared, 0)
    inference.service.request_preparation("live")
    wait_for(lambda: len(inference.attempts) == 1)
    inference.attempts[0].release.set()
    wait_for(lambda: inference.service.preparation_status("shared")["status"] == "activated")
    assert shared._preparation_job is None
    assert inference.service.preparation_status("shared")["active_provider"] == "trt"
    late = inference.register("late")
    frame(late, 0)
    assert inference.created == ["cuda"]
    status = inference.service.preparation_status("late")
    assert status["active_provider"] == "trt" and status["status"] == "activated"
    assert late.provider_status[0].applied_providers == ("trt",)


def test_activation_exception_does_not_kill_inference_worker(inference):
    first = inference.register()
    pinned = inference.register("pinned", "cuda")
    frame(first, 0)
    frame(pinned, 0)
    inference.service.request_preparation("live")
    wait_for(lambda: len(inference.attempts) == 1)
    with patch.object(SharedSessionPool, "activate_prepared", side_effect=RuntimeError("fixture activation error")):
        inference.attempts[0].release.set()
        wait_for(lambda: inference.service.preparation_status("live")["status"] == "failed")
        assert inference.service.worker.is_alive()
        assert frame(first, 1)["camera"].frame_number == 1
        assert frame(pinned, 1)["camera"].frame_number == 1
    assert inference.service.preparation_status("live")["active_provider"] == "cuda"


def test_failed_handoff_can_retry_with_new_generation(inference):
    client = inference.register()
    frame(client, 0)
    inference.service.request_preparation("live")
    wait_for(lambda: len(inference.attempts) == 1)
    with patch.object(OnnxSession, "adopt_prepared_backend", side_effect=ValueError("fixture identity mismatch")):
        inference.attempts[0].release.set()
        wait_for(lambda: inference.service.preparation_status("live")["status"] == "failed")
    assert inference.service.preparation_status("live")["can_prepare"]
    inference.service.request_preparation("live")
    wait_for(lambda: len(inference.attempts) == 2)
    assert inference.attempts[1].ticket.generation == 1
    inference.attempts[1].release.set()
    wait_for(lambda: inference.service.preparation_status("live")["status"] == "activated")


def test_cleanup_queue_failure_retains_resource_without_stopping_clients(inference):
    client = inference.register()
    frame(client, 0)
    inference.service.request_preparation("live")
    wait_for(lambda: len(inference.attempts) == 1)
    with patch.object(inference.service._preparation, "retire", side_effect=RuntimeError("fixture queue unavailable")):
        inference.attempts[0].release.set()
        wait_for(lambda: inference.service.preparation_status("live")["status"] == "activated")
        assert inference.service._retirements
        assert frame(client, 1)["camera"].frame_number == 1
        assert inference.service.worker.is_alive()
    wait_for(lambda: not inference.service._retirements)


def test_provider_diagnostic_failure_does_not_misreport_activated_backend(inference):
    client = inference.register()
    pinned = inference.register("pinned", "cuda")
    frame(client, 0)
    frame(pinned, 0)
    inference.service.request_preparation("live")
    wait_for(lambda: len(inference.attempts) == 1)
    with patch("freemocap.core.tracking.execution_providers.inspect_tracker_providers",
               side_effect=RuntimeError("fixture diagnostic failure")):
        inference.attempts[0].release.set()
        wait_for(lambda: inference.service.preparation_status("live")["status"] == "activated")
        status = inference.service.preparation_status("live")
        assert status["active_provider"] == "trt"
        assert status["error"] == "fixture diagnostic failure"
        assert frame(pinned, 1)["camera"].frame_number == 1
        assert inference.service.worker.is_alive()
