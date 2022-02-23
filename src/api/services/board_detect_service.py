from typing import NamedTuple

from src.core_processor.board_detection.board_detection import BoardDetection


class ImageResponse(NamedTuple):
    image: bytes
    webcam_id: str


class BoardDetectService:
    async def run(self):
        await BoardDetection().process()

    async def run_as_loop(self, cb=None):
        await BoardDetection().process_as_frame_loop(cb)
