"""HTTP preparation controls record intent without touching native sessions."""

from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from freemocap.api.http.onnx.onnx_router import onnx_router


@pytest.fixture
def preparation_api(monkeypatch):
    snapshot = dict(pipeline_id="live", status="idle", phase="idle", elapsed_seconds=0,
                    can_prepare=True, can_cancel=False, requested_provider="trt", active_provider="cuda")
    service = Mock()
    service.preparation_status.return_value = snapshot
    monkeypatch.setattr("freemocap.app.freemocap_application.get_freemocap_app",
                        lambda: SimpleNamespace(inference_service=service))
    app = FastAPI()
    app.include_router(onnx_router, prefix="/freemocap")
    with TestClient(app) as client:
        yield client, service, snapshot


def test_status_is_observation_only_and_preserves_requested_vs_active(preparation_api):
    client, service, _ = preparation_api
    response = client.get("/freemocap/onnx/preparation/live")
    assert response.status_code == 200
    assert response.json()["requested_provider"] == "trt"
    assert response.json()["active_provider"] == "cuda"
    service.request_preparation.assert_not_called()
    service.cancel_preparation.assert_not_called()


def test_stop_reports_incomplete_cleanup_instead_of_success(preparation_api):
    client, service, snapshot = preparation_api
    snapshot.update(status="stopping", phase="stopping", can_prepare=False, can_cancel=False)
    response = client.post("/freemocap/onnx/preparation/live/stop")
    assert response.status_code == 200 and response.json()["status"] == "stopping"
    service.cancel_preparation.assert_called_once_with("live")


@pytest.mark.parametrize("endpoint,method", [("", "request_preparation"), ("/stop", "cancel_preparation")])
def test_invalid_transition_returns_conflict_and_does_not_fabricate_status(preparation_api, endpoint, method):
    client, service, _ = preparation_api
    getattr(service, method).side_effect = ValueError("Preparation is unavailable for this pipeline")
    response = client.post(f"/freemocap/onnx/preparation/live{endpoint}")
    assert response.status_code == 409
    assert "unavailable" in response.json()["detail"]
    service.preparation_status.assert_not_called()
