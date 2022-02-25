from freemocap.prod.cam.cam_detection import DetectPossibleCameras

if __name__ == "__main__":
    c = DetectPossibleCameras()
    available_cameras = c.find_available_cameras()
    open_cv_cameras = []
    #
    # for cam in available_cameras.cams_to_use:
    #     port_number = cam.port_number
    #     options = OpenCVCameraOptions(
    #         port_number=cam.port_number
    #     )
    #     cv_cam = OpenCVCamera()


