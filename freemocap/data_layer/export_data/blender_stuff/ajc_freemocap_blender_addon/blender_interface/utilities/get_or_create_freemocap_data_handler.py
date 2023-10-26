from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.handler import FreemocapDataHandler

FREEMOCAP_DATA_HANDLER = None


def get_or_create_freemocap_data_handler(recording_path: str):
    global FREEMOCAP_DATA_HANDLER
    if FREEMOCAP_DATA_HANDLER is None:
        FREEMOCAP_DATA_HANDLER = FreemocapDataHandler.from_recording_path(recording_path=recording_path)
    return FREEMOCAP_DATA_HANDLER


def create_freemocap_data_handler(recording_path: str):
    global FREEMOCAP_DATA_HANDLER
    FREEMOCAP_DATA_HANDLER = FreemocapDataHandler.from_recording_path(recording_path=recording_path)
    return FREEMOCAP_DATA_HANDLER
