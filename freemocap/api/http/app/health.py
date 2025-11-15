import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
health_router = APIRouter()


@health_router.get("/health", summary="Hello👋", tags=['App'])
def healthcheck_endpoint():
    """
    A simple endpoint to show the server is alive and happy
    """

    return "Hello👋"
