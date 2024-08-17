import logging
from typing import Optional, List, Union

logger = logging.getLogger(__name__)


class Controller:
    def __init__(self,
                 ) -> None:
        super().__init__()

    def close(self):
        logger.debug(f"Closing Controller...")
        pass


CONTROLLER = None

def create_controller() -> Controller:
    global CONTROLLER
    if not CONTROLLER:
        CONTROLLER = Controller()
    return CONTROLLER


def get_controller() -> Controller:
    global CONTROLLER
    if not isinstance(CONTROLLER, Controller):
        raise ValueError("Controller not created!")
    return CONTROLLER
