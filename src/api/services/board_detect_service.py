from typing import NamedTuple

from src.cameras.multicam_manager import CVCameraManager
from src.core_processor.camera_calibration.charuco_board_detection.board_detection import BoardDetector


class ImageResponse(NamedTuple):
    image: bytes
    webcam_id: str


class BoardDetectService:
    def __init__(self, cam_manager: CVCameraManager = CVCameraManager()):
        self._cam_manager = cam_manager

    async def run(self):
        return BoardDetector(self._cam_manager).process()

    async def run_detection_on_cam_id(self, webcam_id: str, cb=None):
        await BoardDetector(self._cam_manager).process_by_cam_id(webcam_id, cb)
