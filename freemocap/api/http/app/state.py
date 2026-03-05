"""
HTTP endpoint serving the current FreeMoCapSettings from SettingsManager.

Useful for initial hydration before the WebSocket connects, and
as a polling fallback for clients that don't use WebSocket.
"""
import logging

from fastapi import APIRouter

from freemocap.app.freemocap_application import get_freemocap_app

logger = logging.getLogger(__name__)
state_router = APIRouter()


@state_router.get("/settings", summary="Current Settings State", tags=["App"])
def settings_state_endpoint() -> dict:
    """
    Serve the current settings blob (same payload shape as
    the `settings/state` WebSocket message).
    """
    logger.api("Serving settings state from `/settings` endpoint...")
    app = get_freemocap_app()
    app.settings_manager.update_from_app(app)
    return app.settings_manager.get_state_message()
