from freemocap.api.http.app.health import health_router
from freemocap.api.http.app.shutdown import app_shutdown_router
from freemocap.api.http.app.state import state_router
from freemocap.api.http.ui.ui_router import ui_router
from freemocap.api.websocket.websocket_connect import freemocap_websocket_router
from skellycam import SKELLYCAM_ROUTERS


FREEMOCAP_ROUTERS = {
    "/ui": {
        "ui": ui_router
    },
    "/app": {
        "health": health_router,
        "state": state_router,
        "shutdown": app_shutdown_router
    },
    "/websocket": {
        "connect": freemocap_websocket_router
    },

    **SKELLYCAM_ROUTERS
}
