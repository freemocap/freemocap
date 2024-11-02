import logging
import os
import signal

from fastapi import APIRouter

logger = logging.getLogger(__name__)
app_shutdown_router = APIRouter()


@app_shutdown_router.get("/shutdown", summary="goodbye👋")
def shutdown_server():
    logger.api("Server shutdown complete - Killing process... Bye!👋")
    os.kill(os.getpid(), signal.SIGINT)
