from src.cameras.detection.cam_detection import DetectPossibleCameras
from src.cameras.detection.models import FoundCamerasResponse

# No consumer should call this "private" variable

_available_cameras: FoundCamerasResponse = None


# If you want cams, you call this function
def get_or_create_cams(always_create=False):
    global _available_cameras
    if _available_cameras is None or always_create:
        d = DetectPossibleCameras()
        _available_cameras = d.find_available_cameras()

    return _available_cameras


def get_or_create_cams_list(always_create=False):
    """
    same as `get_or_create_cams` but returns a list of camera ids instead of a FoundCamerasResponse object
    """
    found_cameras_response = get_or_create_cams(always_create=always_create)
    available_cameras_list = [
        this_cam.webcam_id for this_cam in found_cameras_response.cameras_found_list
    ]

    return available_cameras_list
