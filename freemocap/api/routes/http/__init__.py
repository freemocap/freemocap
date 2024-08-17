from freemocap.api.routes.http.health import healthcheck_router
from freemocap.api.routes.websocket.websocket_server import websocket_router

enabled_routers = {
    "healthcheck": healthcheck_router,
    "websocket": websocket_router,
}