from skellycam.api.http.cameras.camera_router import camera_router

from freemocap.api.http.app.debug import debug_router
from freemocap.api.http.app.health import health_router
from freemocap.api.http.app.shutdown import shutdown_router
from freemocap.api.http.app.state import state_router
from freemocap.api.http.calibration.calibration_router import calibration_router
from freemocap.api.http.mocap.mocap_router import mocap_router
from freemocap.api.http.pipelines.pipeline_router import pipeline_router

APP_ROUTERS = [health_router,
               shutdown_router,
               state_router,
               debug_router]

SKELLYCAM_ROUTERS = [
    camera_router,
]

FREEMOCAP_ROUTERS = [pipeline_router,
                     calibration_router,
                     mocap_router
                     ]
