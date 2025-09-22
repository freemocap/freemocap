import logging

from fastapi import APIRouter

from freemocap.freemocap_app.freemocap_application import get_freemocap_app

logger = logging.getLogger(__name__)
app_shutdown_router = APIRouter()


@app_shutdown_router.get("/shutdown", summary="goodbye👋", tags=['App'])
def shutdown_server():
    from freemocap.api.server.server_singleton import get_server_manager
    logger.api("Shutdown requested - Closing camera connections and shutting down server...")
    get_freemocap_app().shutdown_freemocap()

    get_server_manager().shutdown_server()
    logger.api("Server shutdown complete - Killing process... Bye!👋")
