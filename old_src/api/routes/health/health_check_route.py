from fastapi import APIRouter
from pydantic import BaseModel

healthcheck_router = APIRouter()


class HealthCheckResponse(BaseModel):
    message: str = "OK"


@healthcheck_router.get("/health")
def route():
    try:
        return HealthCheckResponse()
    except:
        raise ValueError("Unhealthy")
