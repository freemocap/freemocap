from skellycam.api.http.cameras.camera_router import camera_router

from freemocap.api.http.calibration.calibration_router import calibration_router
from freemocap.api.http.mocap.mocap_router import mocap_router
from freemocap.api.http.pipelines.pipeline_router import pipeline_router

SKELLYCAM_ROUTERS = [
    camera_router,
]

FREEMOCAP_ROUTERS = [pipeline_router,
                     calibration_router,
                     mocap_router
                     ]
