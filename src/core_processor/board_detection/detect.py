import logging

logger = logging.getLogger(__name__)


class BoardDetection:

    def __init__(self):
        pass

    def process(self, message, *args, **kwargs):
        print(message["timestamp"])
