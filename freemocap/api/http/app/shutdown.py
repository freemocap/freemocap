"""
Clean shutdown endpoint with proper async handling.
"""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

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

    This endpoint triggers a graceful shutdown of the entire FreeMoCap system,
    including all camera groups and the server itself.

    Returns:
        JSON response confirming shutdown initiation
    """
    logger.api(f"Shutdown requested via API - {request.url}")

    # The server supervisor observes this flag and runs graceful shutdown.
    request.app.state.global_kill_flag.value = True
    logger.info("Requested server shutdown")
    return JSONResponse(
        content={
            "status": "shutdown_initiated",
            "message": "Server shutting down. Goodbye! 👋"
        },
        status_code=200
    )
