import logging

from fastapi import APIRouter

HELLO_FROM_FREEMOCAP_BACKEND_MESSAGE = {"message": "Hello from the FreeMoCap Backend 💀✨"}

logger = logging.getLogger(__name__)
health_router = APIRouter()


@health_router.get("/healthcheck", summary="Hello👋", tags=['App'])
def healthcheck_endpoint():
    """
    A simple endpoint to greet the user of the FreeMoCap API.

    This can be used as a sanity check to ensure the API is responding.
    """

    logger.api("Hello requested! Deploying Hello!")
    return HELLO_FROM_FREEMOCAP_BACKEND_MESSAGE
