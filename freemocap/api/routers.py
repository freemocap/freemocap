from skellycam.api.http.cameras.camera_router import camera_router
from skellycam.api.http.videos.videos_router import load_videos_router

from freemocap.api.http.pipelines.pipeline_router import pipeline_router

SKELLYCAM_ROUTERS = [
    camera_router,
    load_videos_router,
]

FREEMOCAP_ROUTERS = [pipeline_router]
