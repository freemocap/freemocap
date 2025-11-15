"""
Clean shutdown endpoint with proper async handling.
"""
import logging
import os
import signal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from skellycam.utilities.wait_functions import await_100ms

logger = logging.getLogger(__name__)

shutdown_router = APIRouter(tags=["App"])


@shutdown_router.get(
    "/shutdown",
    summary="Gracefully shutdown the server",
    response_model=dict[str, str]
)
async def shutdown_server(
        request: Request,
) -> JSONResponse:
    """
    Initiate graceful server shutdown.

    This endpoint triggers a graceful shutdown of the entire SkellyCam system,
    including all camera groups and the server itself.

    Returns:
        JSON response confirming shutdown initiation
    """
    logger.api(f"Shutdown requested via API - {request.url}")

    # Send SIGTERM to ourselves - this triggers the existing shutdown flow
    request.app.state.global_kill_flag.value = True
    await await_100ms()
    os.kill(os.getpid(), signal.SIGTERM)
    logger.info("Sent SIGTERM signal to initiate shutdown")
    return JSONResponse(
        content={
            "status": "shutdown_initiated",
            "message": "Server shutting down. Goodbye! 👋"
        },
        status_code=200
    )
