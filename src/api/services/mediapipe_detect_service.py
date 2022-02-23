from src.core_processor.mediapipe_skeleton_detection.mediapipe_skeleton_detection import (
    MediapipeSkeletonDetection,
)


class MediapipeSkeletonDetectionService:
    def __init__(self, model_complexity: int = 1):
        self._model_complexity = model_complexity

    async def run(self):
        await MediapipeSkeletonDetection().process()

    async def run_as_loop(self, cb):
        await MediapipeSkeletonDetection().process_as_frame_loop(cb)
