import logging
from typing import List

import cv2
from pydantic import BaseModel

CAM_CHECK_NUM = 5

logger = logging.getLogger(__name__)


class RawCamera(BaseModel):
    index: int


class FindAvailableResponse(BaseModel):
    camera_found_count: int
    cams_to_use: List[RawCamera]


class DetectPossibleCameras:

    def find_available_cameras(self) -> FindAvailableResponse:
        capBackend = cv2.CAP_ANY

        cams_to_use_list = []
        for camNum in range(CAM_CHECK_NUM):
            cap = cv2.VideoCapture(camNum, capBackend)
            success, image = cap.read()
            if success:
                try:
                    cams_to_use_list.append(RawCamera(
                        index=camNum,
                    ))
                    logger.info(cap.get(cv2.CAP_PROP_SETTINGS))
                finally:
                    cap.release()

        return FindAvailableResponse(
            camera_found_count=len(cams_to_use_list),
            cams_to_use=cams_to_use_list
        )