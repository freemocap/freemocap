from src.cameras.cam_detection import DetectPossibleCameras

# No consumer should call this "private" variable

_available_cameras = None


# If you want cams, you call this function
def get_or_create_cams():
    global _available_cameras
    if _available_cameras is None:
        d = DetectPossibleCameras()
        _available_cameras = d.find_available_cameras()

    return _available_cameras
