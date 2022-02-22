from src.core_processor.board_detection.board_detection import BoardDetection


class BoardDetectService:
    async def run(self):
        await BoardDetection().process()
