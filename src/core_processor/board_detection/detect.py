import logging

logger = logging.getLogger(__name__)


class BoardDetection:

    def __init__(self):
        pass

    async def process(self, message, *args, **kwargs):
        # logger.info(message)
        logger.info(message["timestamp"])
