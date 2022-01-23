from src.api.routes.camera.camera_route import camera_router
from src.api.routes.health.health_check_route import healthcheck_router

# REGISTER NEW ROUTES HERE
enabled_routers = [
    healthcheck_router,
    camera_router
]
