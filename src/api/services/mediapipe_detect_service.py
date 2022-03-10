from src.cameras.multicam_manager.cv_camera_manager import CVCameraManager
from src.core_processor.mediapipe_skeleton_detection.mediapipe_skeleton_detection import (
    MediapipeSkeletonDetection,
)


class MediapipeSkeletonDetectionService:
    def __init__(self, cam_manager: CVCameraManager):
        self._cam_manager = cam_manager

    def run(self, model_complexity: int):
        MediapipeSkeletonDetection(self._cam_manager).process(
            model_complexity=model_complexity
        )

    async def run_as_loop(self, webcam_id, cb, model_complexity: int):
        await MediapipeSkeletonDetection(self._cam_manager).process_as_frame_loop(
            webcam_id, model_complexity=model_complexity, cb=cb
        )
