from freemocap.api.routers.http.health import healthcheck_router
from freemocap.api.routers.websocket.websocket_server import websocket_router

enabled_routers = {
    "healthcheck": healthcheck_router,
    "websocket": websocket_router,
}