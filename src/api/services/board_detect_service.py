from src.core_processor.board_detection.detect import BoardDetection


class BoardDetectService:

    async def run(self):
        await BoardDetection().process()
