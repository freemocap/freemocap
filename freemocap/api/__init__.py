from freemocap.api.routers.v0.http.health import healthcheck_router
from freemocap.api.routers.v0.websocket.websocket_server import websocket_router

enabled_routers = {
    "v0": {
        "healthcheck": healthcheck_router,
        "websocket": websocket_router,
    }
}

