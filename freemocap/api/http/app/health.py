import logging
import os

from fastapi import APIRouter

logger = logging.getLogger(__name__)
health_router = APIRouter()


@health_router.get("/health", summary="Health check", tags=['App'])
def healthcheck_endpoint() -> dict:
    """Report that the server is alive and which OS process it is running as.

    The PID lets the UI display the concrete server process it is talking to,
    rather than inferring a separate true/false "server connected" state.
    """
    return {"alive": True, "pid": os.getpid()}
