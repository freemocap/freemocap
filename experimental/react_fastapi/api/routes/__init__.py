from src.api.routes.camera.cam_data_ws import cam_ws_router
from src.api.routes.camera.camera_route import camera_router
from src.api.routes.health.health_check_route import healthcheck_router
from src.api.routes.home.home import home_router
from src.api.routes.session.session_router import session_router
from src.api.routes.startup.startup import startup_router

# REGISTER NEW ROUTES HERE
enabled_routers = [
    healthcheck_router,
    camera_router,
    cam_ws_router,
    startup_router,
    home_router,
    session_router,
]
