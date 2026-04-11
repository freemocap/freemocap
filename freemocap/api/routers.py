from skellycam.api.http.cameras.camera_router import camera_router
from skellycam.api.http.playback.playback_router import playback_router

from freemocap.api.http.app.health import health_router
from freemocap.api.http.app.shutdown import shutdown_router
from freemocap.api.http.blender.blender_router import blender_router
from freemocap.api.http.calibration.calibration_router import calibration_router
from freemocap.api.http.mocap.mocap_router import mocap_router
from freemocap.api.http.realtime.realtime_router import realtime_router

APP_ROUTERS = [health_router,
               shutdown_router]

SKELLYCAM_ROUTERS = [
    camera_router,
    playback_router
]

FREEMOCAP_ROUTERS = [realtime_router,
                     calibration_router,
                     mocap_router,
                     blender_router,
                     ]
