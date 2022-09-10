import logging
import platform

import cv2

from src.cameras.detection.models import FoundCamerasResponse

CAM_CHECK_NUM = 20  # please give me a reason to increase this number ;D

logger = logging.getLogger(__name__)


class DetectPossibleCameras:
    def find_available_cameras(self) -> FoundCamerasResponse:
        cv2_backend = self._determine_backend()

        cams_to_use_list = []
        for cam_id in range(CAM_CHECK_NUM):
            cap = cv2.VideoCapture(cam_id, cv2_backend)
            success, image = cap.read()

            if success:
                if image is not None:
                    try:
                        logger.debug(f"Camera found at port number {cam_id}")
                        cams_to_use_list.append(str(cam_id))
                    finally:
                        cap.release()

        return FoundCamerasResponse(
            number_of_cameras_found=len(cams_to_use_list),
            cameras_found_list=cams_to_use_list,
            cv2_backend=cv2_backend,
        )

    def _determine_backend(self):
        if platform.system() == "Windows":
            return cv2.CAP_DSHOW
        else:
            return cv2.CAP_ANY
