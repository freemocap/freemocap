"""Camera capture commands retain their mocap/calibration behavior."""
from fastapi import APIRouter

from freemocap.api.http.mocap import mocap_router as mocap
from freemocap.api.http.calibration import calibration_router as calibration
from freemocap.api.http.capture.capture_models import CaptureStopped

capture_router = APIRouter(prefix='/capture', tags=['Capture'])
for path, handler in (
    ('/mocap/start', mocap.start_mocap_recording),
    ('/calibration/start', calibration.start_calibration_recording),
):
    capture_router.add_api_route(path, handler, methods=['POST'], operation_id=f'capture_{handler.__name__}')

for path, handler in (
    ('/mocap/stop', mocap.stop_mocap_recording),
    ('/calibration/stop', calibration.stop_calibration_recording),
):
    capture_router.add_api_route(path, handler, methods=['POST'], response_model=CaptureStopped,
                                 operation_id=f'capture_{handler.__name__}')
