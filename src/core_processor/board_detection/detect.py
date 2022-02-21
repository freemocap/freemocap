import asyncio
import logging

import cv2
import numpy as np

from src.core_processor.processor import create_opencv_cams

aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_250)
charuco_length = 7
charuco_width = 5

board = cv2.aruco.CharucoBoard_create(charuco_length, charuco_width, 1, .8, aruco_dict)
num_charuco_corners = (charuco_length - 1) * (charuco_width - 1)


class BoardDetection:

    async def process(self):
        logger = logging.getLogger(__name__)
        cv_cams = create_opencv_cams()

        for cv_cam in cv_cams:
            cv_cam.start_frame_capture()

        while True:
            for cv_cam in cv_cams:
                success, frame, timestamp = cv_cam.latest_frame()
                if not success:
                    continue

                if frame is None:
                    continue

                port_number = str(cv_cam.port_number)
                print(
                    f'got image of shape {frame.shape} from camera at port {port_number}')
                charuco_corners, charuco_ids, aruco_square_corners, aruco_square_ids = \
                    self.detect_charuco_board(frame)
                # TODO - Pull out timestamps per frame and calculate fps to display on image
                success_bool = self.annotate_image_with_charuco_data(frame, port_number,
                    charuco_corners, charuco_ids)

                cv2.polylines(frame, np.int32([charuco_corners]), True, (0, 100, 255), 2)

                cv2.imshow(port_number, frame)
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

    def annotate_image_with_charuco_data(self, image, port_number, charuco_corners,
        charuco_ids) -> bool:

        full_charuco_detected_on_this_frame = False
        if len(charuco_ids) == num_charuco_corners:
            full_charuco_detected_on_this_frame = True

        image_w_markers = cv2.aruco.drawDetectedCornersCharuco(image,
            np.array(charuco_corners),
            np.array(charuco_ids),
            (0, 255, 125, 255))  # yellow? I
        # think cv2 uses BGR instead of RGB?

        this_cam_name = "Camera " + str(port_number)

        text_to_write_on_this_camera = ''
        current_cam_corner_count_str = this_cam_name + ": " + str(
            len(charuco_ids)) + " of " + str(
            num_charuco_corners) + " ChAruco Corner Points detected | Full Board Detected: " + str(
            full_charuco_detected_on_this_frame)
        # TODO - Determine 'shared views' (i.e. frames in which a full board is detected by 2
        #  cameras)
        # TODO - self.determine_shared_charuco_board_views()
        # this_cam_shared_views_str = " | Shared Views: " + str(
        #     each_cameras_shared_board_view_count_total)
        text_to_write_on_this_camera = current_cam_corner_count_str

        position = (10, 50)
        cv2.putText(
            image_w_markers,  # numpy array on which text is written
            text_to_write_on_this_camera,  # text
            position,  # position at which writing has to start
            cv2.FONT_HERSHEY_SIMPLEX,  # font family
            .5,  # font size
            (30, 10, 0, 255),  # font color
            2)  # font stroke (draw a darker heavier font beneath a lighter/thinner copy for
        # readability)

        cv2.putText(
            image_w_markers,  # numpy array on which text is written
            text_to_write_on_this_camera,  # text
            position,  # position at which writing has to start
            cv2.FONT_HERSHEY_SIMPLEX,
            # font family (very limited selection, i think there's some interesting CV history
            # here...)
            .5,  # font size
            (209, 180, 0, 255),  # font color
            1)  # font stroke

        if full_charuco_detected_on_this_frame:
            cv2.polylines(image_w_markers, np.int32([charuco_corners]), False, (0, 100, 255), 2)
            # for these_corners in charuco_points_from_previous_frames:
            # if len(these_corners)>0:
            #     cv2.polylines(image_w_markers, np.int32([these_corners]), True, (0,100,255,
            #     255/2), 2)

        return True

    def determine_shared_charuco_board_views(self):
        pass
        # # determine paired board views
        # for this_cam_num in range(multi_cam.num_cams):
        #     if full_charuco_detected_on_this_frame[this_cam_num]:
        #         for this_other_camera_num in range(multi_cam.num_cams):
        #             if this_other_camera_num != this_cam_num:
        #                 if full_charuco_detected_on_this_frame[this_other_camera_num]:
        #                     each_cameras_shared_board_view_count_array[this_cam_num,
        #                     this_other_camera_num] += 1
        # each_cameras_shared_board_view_count_total = np.sum(
        # each_cameras_shared_board_view_count_array, axis=1)
        # # print(each_cameras_shared_board_view_count)
        #
        # for this_pair_num, this_cam_pair in enumerate(camera_pair_list):
        #     camera_one_id = this_cam_pair[0]
        #     camera_two_id = this_cam_pair[1]
        #
        #     if full_charuco_detected_on_this_frame[camera_one_id] and
        #     full_charuco_detected_on_this_frame[
        #         camera_two_id]:
        #         camera_pair_joint_view_count[this_pair_num] += 1


if __name__ == "__main__":
    asyncio.run(BoardDetection().process())
