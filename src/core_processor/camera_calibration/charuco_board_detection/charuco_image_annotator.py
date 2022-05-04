from typing import List

import cv2
import numpy as np

from src.core_processor.camera_calibration.charuco_board_detection.dataclasses.charuco_view_data import CharucoViewData


def _board_text(
        charuco_ids: List[int],
        num_charuco_corners: int,
        full_board_detected_bool: bool,
):
    num_ids_as_str = str(len(charuco_ids))
    num_corners_as_str = str(num_charuco_corners)
    text = (
        f"{num_ids_as_str} of {num_corners_as_str} Charuco Corner Points Detected "
        f"| Full Board Detected: {full_board_detected_bool}"
    )
    return text


def annotate_image_with_charuco_data(
        image,
        charuco_view_data: CharucoViewData,
        number_of_charuco_corners: int) -> bool:

    annotated_image = cv2.aruco.drawDetectedCornersCharuco(
        image,
        np.array(charuco_view_data.charuco_corners),
        np.array(charuco_view_data.charuco_ids),
        (0, 255, 125, 255)
    )  # yellow? I
    # think cv2 uses BGR instead of RGB?


    current_cam_corner_count_str = _board_text(
        charuco_view_data.charuco_ids,
        number_of_charuco_corners,
        charuco_view_data.full_board_found,
    )
    # TODO - Determine 'shared views' (i.e. frames in which a full board is detected by 2
    #  cameras)
    # TODO - self.determine_shared_charuco_board_views()
    # this_cam_shared_views_str = " | Shared Views: " + str(
    #     each_cameras_shared_board_view_count_total)
    text_to_write_on_this_camera = current_cam_corner_count_str

    position = (10, 50)
    cv2.putText(
        annotated_image,  # numpy array on which text is written
        text_to_write_on_this_camera,  # text
        position,  # position at which writing has to start
        cv2.FONT_HERSHEY_SIMPLEX,  # font family
        0.5,  # font size
        (30, 10, 0, 255),  # font color
        2,
    )  # font stroke (draw a darker heavier font beneath a lighter/thinner copy for
    # readability)

    cv2.putText(
        annotated_image,  # numpy array on which text is written
        text_to_write_on_this_camera,  # text
        position,  # position at which writing has to start
        cv2.FONT_HERSHEY_SIMPLEX,
        # font family (very limited selection, i think there's some interesting CV history
        # here...)
        0.5,  # font size
        (209, 180, 0, 255),  # font color
        1,
    )  # font stroke

    if charuco_view_data.full_board_found:
        cv2.polylines(
            annotated_image, np.int32([charuco_view_data.charuco_corners]), False, (0, 100, 255), 2
        )
