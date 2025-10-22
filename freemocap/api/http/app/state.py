import logging

from fastapi import APIRouter

from skellycam.skellycam_app.skellycam_app import get_skellycam_app

logger = logging.getLogger(__name__)
state_router = APIRouter()


@state_router.get("/state", summary="Application State", tags=['App'])
def app_state_endpoint():
    """
    A simple endpoint that serves the current state of the application
    """
    logger.api("Serving application state from `app/state` endpoint...")

    return get_skellycam_app().state_dto()
