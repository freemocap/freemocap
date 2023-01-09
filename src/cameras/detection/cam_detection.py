import logging
import platform
import time

import cv2
from old_src.cameras.detection.models import FoundCamerasResponse

CAM_CHECK_NUM = 20  # please give me a reason to increase this number ;D

logger = logging.getLogger(__name__)


class DetectPossibleCameras:
    def find_available_cameras(self) -> FoundCamerasResponse:
        cv2_backend = self._determine_backend()

        cams_to_use_list = []
        caps_list = []
        for cam_id in range(CAM_CHECK_NUM):
            cap = cv2.VideoCapture(cam_id, cv2_backend)
            success, image = cap.read()
            time0 = time.perf_counter()
            logger.debug(
                f"Trying to read from camera {cam_id} using `cv2_backend`: {cv2_backend}: success={success}, image.__class__ ={image.__class__}"
            )
            if success:
                if image is not None:
                    try:
                        success, image = cap.read()
                        time1 = time.perf_counter()

                        if time1 - time0 > 0.5:
                            logger.debug(
                                f"Camera {cam_id} took {time1-time0} seconds to produce a 2nd frame. It might be a virtual camera Skipping it."
                            )
                            continue  # skip to next port number

                        logger.debug(
                            f"Camera found at port number {cam_id}: success={success}, image.shape={image.shape},  cap={cap}"
                        )
                        cams_to_use_list.append(str(cam_id))
                        caps_list.append(cap)

                        # # # for debugging - uncomment to show cameras as they are detected
                        # while True:
                        #     cv2.imshow(f"Camera {cam_id} - press 'q' to continue", image)
                        #     if cv2.waitKey(1) & 0xFF == ord('q'):
                        #         break
                        #     success, image = cap.read()

                    except Exception as e:
                        logger.error(
                            f"Exception raised when looking for a camera at port{cam_id}: {e}"
                        )

        for cap in caps_list:
            logger.debug(f"Releasing cap {cap}")
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
