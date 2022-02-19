import logging

import cv2
import numpy as np

from aiomultiprocess import Process
from aiomultiprocess.types import Queue

from src.core_processor.processor import ImagePayload


from rich import inspect


# aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_250)
# charuco_length = 7
# charuco_width = 5

# board = cv2.aruco.CharucoBoard_create(charuco_length, charuco_width, 1, .8, aruco_dict)
# num_charuco_corners = (charuco_length-1) * (charuco_width-1)


class BoardDetection:

    async def create_new_process_for_run(self, queue: Queue):
        p = Process(target=self.process, args=(queue,))
        p.start()
        await p.join()

    async def process(self, queue: Queue):
        logger = logging.getLogger(__name__)
        while True:
            message = None
            try:
                message = queue.get(timeout=1)  # type: ImagePayload
            except Exception as e:
                pass
            print('got message from the queue')
            

            
            if not message:
                continue
            
            frames = message.frames
            print(f'got image of shape {f.image.shape}')
            
            for f in frames:
                # charuco_corners, charuco_ids, aruco_square_corners, aruco_square_ids = self.detect_charuco_board(f.image)
                # cv2.polylines(f.image, np.int32([charuco_corners]), True, (0,100,255), 2)

                cv2.imshow(str(f.port_number), f.image)
                exit_key = cv2.waitKey(1)
                if exit_key == 27:
                    break


    def detect_charuco_board(self, image):
        """
        Charuco base pose estimation.
        more-or-less copied from - https://mecaruco2.readthedocs.io/en/latest/notebooks_rst/Aruco
        /sandbox/ludovic/aruco_calibration_rotation.html
        """
        charuco_corners = []
        charuco_ids = []
    
        # SUB PIXEL CORNER DETECTION CRITERION
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.00001)
    
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        aruco_square_corners, aruco_square_ids, rejectedImgPoints = cv2.aruco.detectMarkers(gray,
            aruco_dict)
    
        if len(aruco_square_corners) > 0:
            # SUB PIXEL DETECTION
            for this_corner in aruco_square_corners:
                cv2.cornerSubPix(gray, this_corner,
                    winSize=(3, 3),
                    zeroZone=(-1, -1),
                    criteria=criteria)
            res2 = cv2.aruco.interpolateCornersCharuco(aruco_square_corners, aruco_square_ids, gray,
                board)
    
            if res2[1] is not None and res2[2] is not None and len(res2[1]) > 3:
                charuco_corners = res2[1]
                charuco_ids = res2[2]
    
        return charuco_corners, charuco_ids, aruco_square_corners, aruco_square_ids

