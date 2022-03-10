import logging
import platform

import cv2

from src.cameras.detection.models import FoundCamerasResponse, RawCamera

CAM_CHECK_NUM = 5

logger = logging.getLogger(__name__)


class DetectPossibleCameras:
    def find_available_cameras(self) -> FoundCamerasResponse:
        cv2_backend = self._determine_backend()

        cams_to_use_list = []
        for cam_id in range(CAM_CHECK_NUM):
            cap = cv2.VideoCapture(cam_id, cv2_backend)
            success, image = cap.read()

            if success:
                try:
                    cams_to_use_list.append(
                        RawCamera(
                            webcam_id=cam_id,
                        )
                    )
                finally:
                    cap.release()

        return FoundCamerasResponse(
            camera_found_count=len(cams_to_use_list),
            cams_to_use=cams_to_use_list,
            cv2_backend=cv2_backend,
        )

    def _determine_backend(self):
        if platform.system() == "Windows":
            return cv2.CAP_DSHOW
        else:
            return cv2.CAP_ANY
