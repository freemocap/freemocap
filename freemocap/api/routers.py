from skellycam.api.http.cameras.camera_router import camera_router
from skellycam.api.http.videos.videos_router import load_videos_router
from skellycam.api.websocket.websocket_connect import websocket_router

from freemocap.api.http.app.health import health_router
from freemocap.api.http.app.shutdown import shutdown_server

SKELLYCAM_ROUTERS = [
    camera_router,
    load_videos_router,
]


FREEMOCAP_ROUTERS = [websocket_router, health_router]