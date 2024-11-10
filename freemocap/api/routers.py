from skellycam import SKELLYCAM_ROUTERS

from freemocap.api.http.app.health import health_router
from freemocap.api.http.app.shutdown import app_shutdown_router
from freemocap.api.http.app.state import state_router
from freemocap.api.http.ui.ui_router import ui_router

FREEMOCAP_ROUTERS = {
    "/ui": {
        "ui": ui_router
    },
    "/app": {
        "health": health_router,
        "state": state_router,
        "shutdown": app_shutdown_router
    },
    **SKELLYCAM_ROUTERS
}
