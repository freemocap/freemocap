import logging
import platform

import cv2

from src.cameras.detection.models import FoundCamerasResponse

CAM_CHECK_NUM = 20

logger = logging.getLogger(__name__)


class DetectPossibleCameras:
    def find_available_cameras(self) -> FoundCamerasResponse:
        cv2_backend = self._determine_backend()

        cams_to_use_list = []
        for this_usb_port_number in range(CAM_CHECK_NUM):
            cap = cv2.VideoCapture(this_usb_port_number, cv2_backend)
            success, image = cap.read()

            if success:
                try:
                    cams_to_use_list.append(this_usb_port_number)
                finally:
                    cap.release()

        return FoundCamerasResponse(
            number_of_cameras_found=len(cams_to_use_list),
            list_of_usb_port_numbers_with_cameras_attached=cams_to_use_list,
            cv2_backend=cv2_backend,
        )

    @staticmethod
    def _determine_backend():
        if platform.system() == "Windows":
            return cv2.CAP_DSHOW
        else:
            return cv2.CAP_ANY
