import logging

from ajc_freemocap_blender_addon.blender_interface.utilities.get_or_create_freemocap_data_handler import \
    create_freemocap_data_handler
from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.handler import \
    FreemocapDataHandler

logger = logging.getLogger(__name__)


def load_freemocap_data(
        recording_path: str,
) -> FreemocapDataHandler:
    logger.info(f"Loading freemocap_data from {recording_path}....")

    try:
        handler = create_freemocap_data_handler(recording_path=recording_path)
        logger.info(f"Loaded freemocap_data from {recording_path} successfully: \n{handler}")
        handler.mark_processing_stage("original_from_file")
    except Exception as e:
        logger.error(f"Failed to load freemocap freemocap_data: {e}")
        logger.exception(e)
        raise e

    return handler
