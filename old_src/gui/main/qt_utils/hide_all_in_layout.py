import logging

logger = logging.getLogger(__name__)


def hide_all_in_layout(layout):
    logger.debug(f"Hiding everything in  layout {layout}")
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            logger.debug(f"Hiding child widget {child.widget}")
            child.widget().hide()
        elif child.layout():
            hide_all_in_layout(child.layout())
            logger.debug(f"Hiding sub-layout {child.layout}")
            child.layout().hide()
