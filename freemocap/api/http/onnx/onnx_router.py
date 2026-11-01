import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

onnx_router = APIRouter(prefix="/onnx", tags=["Onnx"])


class AvailableExecutionProvidersResponse(BaseModel):
    available: list[str]


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
