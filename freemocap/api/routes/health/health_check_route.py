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

@healthcheck_router.get("/health/doublehealth")
def double_route():
    health_response = route()
    if health_response:
        health_response.message = "wow SO ok!"
        return health_response

    raise ValueError("Unheeeaaaallthy")
