import logging


def logging_setup():
    logging.getLogger("websockets.client").setLevel(level=logging.INFO)
