import logging
import platform
from typing import List

import cv2
from pydantic import BaseModel

CAM_CHECK_NUM = 5

logger = logging.getLogger(__name__)


class RawCamera(BaseModel):
    port_number: int


class FindAvailableResponse(BaseModel):
    camera_found_count: int
    cams_to_use: List[RawCamera]
    cv2_backend: int


class DetectPossibleCameras:

    def find_available_cameras(self) -> FindAvailableResponse:
        cv2_backend = self._determine_backend()

        cams_to_use_list = []
        for camNum in range(CAM_CHECK_NUM):
            cap = cv2.VideoCapture(camNum, cv2_backend)
            success, image = cap.read()
            if success:
                logger.info(f"We found one: {camNum}")
                try:
                    cams_to_use_list.append(RawCamera(
                        port_number=camNum,
                    ))
                    logger.info(cap.get(cv2.CAP_PROP_SETTINGS))
                finally:
                    cap.release()

        return FindAvailableResponse(
            camera_found_count=len(cams_to_use_list),
            cams_to_use=cams_to_use_list,
            cv2_backend=cv2_backend
        )

    def _determine_backend(self):
        if platform.system() == 'Windows':
            return cv2.CAP_DSHOW
        else:
            return cv2.CAP_ANY
