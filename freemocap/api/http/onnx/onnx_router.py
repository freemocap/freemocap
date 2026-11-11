import logging
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

onnx_router = APIRouter(prefix="/onnx", tags=["Onnx"])


class AvailableExecutionProvidersResponse(BaseModel):
    available: list[str]


@onnx_router.get("/execution_providers")
def get_available_execution_providers() -> AvailableExecutionProvidersResponse:
    """List the ONNX Runtime execution providers usable on this machine, in preference order."""
    try:
        # Imported lazily: pulls in the onnxruntime native library.
        import onnxruntime as ort
        from skellytracker.core.sessions.ort_session_utils import _PROVIDER_EP_NAME

        installed = set(ort.get_available_providers())
        available = [
            name
            for name, ep_name in _PROVIDER_EP_NAME.items()
            if ep_name in installed and not (name == "coreml" and sys.platform != "darwin")
        ]
        return AvailableExecutionProvidersResponse(available=available)
    except Exception as e:
        logger.exception(f"Error listing ONNX execution providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))
