"""HTTP startup outcomes and clocks remain truthful through asynchronous cleanup."""

import asyncio
from threading import Event
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from skellycam.core.camera.config.camera_config import CameraConfig

from freemocap.api.http.realtime import realtime_router as routes
from freemocap.app.freemocap_application import FreemocapApplication, RealtimeStartupConfigurationError, RealtimeStartupStopped
from freemocap.core.pipeline.realtime.startup_status import RealtimeStartupStatus


def http_app(monkeypatch, service):
    monkeypatch.setattr(routes, "get_freemocap_app", lambda: service)
    monkeypatch.setattr(routes, "logger", Mock())
    app = FastAPI()
    app.include_router(routes.realtime_router, prefix="/freemocap")
    return app


@pytest.mark.parametrize("error,expected", [(RealtimeStartupStopped("Stopped at a safe boundary"), 409),
                                          (RuntimeError("camera failed"), 500)])
def test_apply_distinguishes_intentional_stop_from_startup_failure(monkeypatch, error, expected):
    service = SimpleNamespace(create_or_update_realtime_pipeline=AsyncMock(side_effect=error))
    config = CameraConfig(camera_id="camera", camera_index=0)
    with TestClient(http_app(monkeypatch, service)) as client:
        response = client.post("/freemocap/realtime/apply", json={
            "cameraConfigs": {config.camera_id: config.model_dump(mode="json")},
        })
    assert response.status_code == expected
    if expected == 409:
        assert response.json()["detail"] == {"code": "startup_stopped", "message": str(error)}
    else:
        assert "camera failed" in response.json()["detail"]


def test_unsupported_startup_configuration_returns_actionable_conflict(monkeypatch):
    error = RealtimeStartupConfigurationError("Invalid tracker configuration")
    service = SimpleNamespace(create_or_update_realtime_pipeline=AsyncMock(side_effect=error))
    config = CameraConfig(camera_id="camera", camera_index=0)
    with TestClient(http_app(monkeypatch, service)) as client:
        response = client.post("/freemocap/realtime/apply", json={
            "cameraConfigs": {config.camera_id: config.model_dump(mode="json")},
        })
    assert response.status_code == 409
    assert response.json()["detail"] == str(error)


def test_phase_clock_excludes_model_loading_and_does_not_reset_on_poll(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("freemocap.core.pipeline.realtime.startup_status.monotonic", lambda: clock[0])
    startup = RealtimeStartupStatus()
    startup.begin()
    startup.pipeline_created("pipeline")
    inference = {"status": "running", "phase": "warming_models", "phase_elapsed_seconds": 10.0,
                 "message": "Warming pose", "error": None}
    service = SimpleNamespace(startup_status=startup, inference_service=SimpleNamespace(startup_status=lambda _: inference))
    with TestClient(http_app(monkeypatch, service)) as client:
        clock[0] = 110.0
        warming = client.get("/freemocap/realtime/startup").json()
        assert warming["phase"] == "warming_models" and warming["phase_elapsed_seconds"] == 10.0
        clock[0] = 140.0
        inference.update(status="ready", phase="running", phase_elapsed_seconds=0.0)
        waiting = client.get("/freemocap/realtime/startup").json()
        assert waiting["status"] == "running" and waiting["phase"] == "waiting_for_frames"
        assert waiting["elapsed_seconds"] == 40.0 and waiting["phase_elapsed_seconds"] == 0.0
        clock[0] = 143.0
        assert client.get("/freemocap/realtime/startup").json()["phase_elapsed_seconds"] == 3.0
        clock[0] = 156.0
        assert client.get("/freemocap/realtime/startup").json()["delayed"]
        startup.record_frame_delivery("pipeline")
        assert client.get("/freemocap/realtime/startup").json()["status"] == "ready"


def test_stale_inference_failure_cannot_overwrite_a_new_startup(monkeypatch):
    startup = RealtimeStartupStatus()
    startup.begin()
    startup.pipeline_created("old")

    def inference(_):
        startup.begin()
        startup.pipeline_created("new")
        return {"status": "failed", "phase": "failed", "phase_elapsed_seconds": 0.0,
                "message": "Old worker failed", "error": "old failure"}

    service = SimpleNamespace(startup_status=startup, inference_service=SimpleNamespace(startup_status=inference))
    with TestClient(http_app(monkeypatch, service)) as client:
        response = client.get("/freemocap/realtime/startup").json()
    assert response["pipeline_id"] == "new" and response["status"] == "running"
    assert response["error"] is None


def test_inference_failure_is_terminal_and_cannot_be_marked_ready_by_late_frame(monkeypatch):
    startup = RealtimeStartupStatus()
    startup.begin()
    startup.pipeline_created("pipeline")
    service = SimpleNamespace(startup_status=startup, inference_service=SimpleNamespace(startup_status=lambda _: {
        "status": "failed", "phase": "loading_models", "phase_elapsed_seconds": 2.0,
        "message": "Loading failed", "error": "provider initialization failed",
    }))
    with TestClient(http_app(monkeypatch, service)) as client:
        failed = client.get("/freemocap/realtime/startup").json()
        assert failed["status"] == "failed" and failed["error"] == "provider initialization failed"
        startup.record_frame_delivery("pipeline")
        assert client.get("/freemocap/realtime/startup").json()["status"] == "failed"


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_stop_after_apply_during_model_load_returns_before_owned_cleanup_finishes(monkeypatch, cleanup_failure):
    service = object.__new__(FreemocapApplication)
    service.startup_status = RealtimeStartupStatus()
    service.startup_status.begin()
    service.startup_status.pipeline_created("pipeline")
    service._realtime_lifecycle_lock = asyncio.Lock()
    service._realtime_startup_operation = None
    service._realtime_stop_task = None
    service._startup_pipeline_owned = True
    service.inference_service = SimpleNamespace(startup_status=lambda _: {
        "status": "running", "phase": "loading_models", "phase_elapsed_seconds": 1.0,
        "message": "Loading pose", "error": None,
    })
    entered, release = Event(), Event()

    def stop(*, pipeline_id):
        assert pipeline_id == "pipeline"
        entered.set()
        assert release.wait(3)
        if cleanup_failure:
            raise RuntimeError("worker still owns resources")
        return True

    service.realtime_pipeline_manager = SimpleNamespace(stop_pipeline=Mock(side_effect=stop))
    with TestClient(http_app(monkeypatch, service)) as client:
        assert client.get("/freemocap/realtime/startup").json()["phase"] == "loading_models"
        response = client.post("/freemocap/realtime/startup/stop")
        try:
            assert response.status_code == 200 and response.json()["status"] == "stopping"
            assert entered.wait(2)
            assert client.get("/freemocap/realtime/startup").json()["status"] == "stopping"
            assert not service._realtime_stop_task.done()
        finally:
            release.set()
        deadline = monotonic() + 2
        while True:
            response = client.get("/freemocap/realtime/startup").json()
            if response["status"] != "stopping":
                break
            assert monotonic() < deadline
            Event().wait(0.005)
        assert response["status"] == ("failed" if cleanup_failure else "stopped")
        if cleanup_failure:
            assert response["error"] == "worker still owns resources"
        service.realtime_pipeline_manager.stop_pipeline.assert_called_once_with(pipeline_id="pipeline")
