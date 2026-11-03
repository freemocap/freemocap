import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

onnx_router = APIRouter(prefix="/onnx", tags=["ONNX"])


class AvailableExecutionProvidersResponse(BaseModel):
    available: list[str]


class PreparationStatusResponse(BaseModel):
    pipeline_id: str
    status: Literal["unavailable", "idle", "queued", "running", "stopping", "ready", "activated", "failed", "cancelled"]
    phase: str
    elapsed_seconds: float
    model_name: str | None = None
    message: str | None = None
    error: str | None = None
    can_prepare: bool
    can_cancel: bool
    requested_provider: str | None = None
    active_provider: str | None = None


def _preparation_action(pipeline_id: str, action: str) -> PreparationStatusResponse:
    from freemocap.app.freemocap_application import get_freemocap_app
    service = get_freemocap_app().inference_service
    try:
        if action == "prepare":
            service.request_preparation(pipeline_id)
        elif action == "stop":
            service.cancel_preparation(pipeline_id)
        return PreparationStatusResponse(**service.preparation_status(pipeline_id))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@onnx_router.get("/preparation/{pipeline_id}", operation_id="onnx_preparation_status")
def preparation_status(pipeline_id: str) -> PreparationStatusResponse:
    """Observe cached preparation state without creating or querying native sessions."""
    return _preparation_action(pipeline_id, "status")


@onnx_router.post("/preparation/{pipeline_id}", operation_id="prepare_onnx")
def prepare_onnx(pipeline_id: str) -> PreparationStatusResponse:
    """Request isolated preparation explicitly, retaining current processing until ready."""
    return _preparation_action(pipeline_id, "prepare")


@onnx_router.post("/preparation/{pipeline_id}/stop", operation_id="stop_onnx_preparation")
def stop_onnx_preparation(pipeline_id: str) -> PreparationStatusResponse:
    """Request preparation cancellation; report stopped only after worker cleanup."""
    return _preparation_action(pipeline_id, "stop")


@onnx_router.get("/execution_providers")
def get_available_execution_providers() -> AvailableExecutionProvidersResponse:
    """List providers advertised by this ONNX build; native library loading is checked at session startup."""
    try:
        from freemocap.core.tracking.execution_providers import advertised_providers
        available = advertised_providers()
        return AvailableExecutionProvidersResponse(available=available)
    except Exception as e:
        logger.exception(f"Error listing ONNX execution providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@onnx_router.get("/session_providers")
def get_session_providers() -> list[dict]:
    """Actual loaded providers for shared live/post-hoc sessions; empty models means pending startup.

    Per-camera process sessions report the same diagnostics in their startup logs.
    """
    from freemocap.app.freemocap_application import get_freemocap_app
    return get_freemocap_app().inference_service.provider_status()
