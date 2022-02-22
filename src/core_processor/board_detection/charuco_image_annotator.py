from typing import List

import cv2
import numpy as np

from src.core_processor.board_detection.charuco_constants import num_charuco_corners


def _board_text(
    cam_name: str,
    charuco_ids: List[int],
    charuco_corners: int,
    charuco_detect_bool: bool,
):
    ids_as_str = str(len(charuco_ids))
    corners_as_str = str(charuco_corners)
    text = (
        f"{cam_name}: {ids_as_str} of {corners_as_str} Charuco Corner Points Detected "
        f"| Full Board Detected: {charuco_detect_bool}"
    )
    return text


def annotate_image_with_charuco_data(
    image, webcam_id: str, charuco_corners, charuco_ids
) -> bool:
    full_charuco_detected_on_this_frame = False

    if len(charuco_ids) == num_charuco_corners:
        full_charuco_detected_on_this_frame = True

    image_w_markers = cv2.aruco.drawDetectedCornersCharuco(
        image, np.array(charuco_corners), np.array(charuco_ids), (0, 255, 125, 255)
    )  # yellow? I
    # think cv2 uses BGR instead of RGB?

    this_cam_name = f"Camera {webcam_id}"

    text_to_write_on_this_camera = ""
    current_cam_corner_count_str = _board_text(
        this_cam_name,
        charuco_ids,
        num_charuco_corners,
        full_charuco_detected_on_this_frame,
    )
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
        0.5,  # font size
        (30, 10, 0, 255),  # font color
        2,
    )  # font stroke (draw a darker heavier font beneath a lighter/thinner copy for
    # readability)

    cv2.putText(
        image_w_markers,  # numpy array on which text is written
        text_to_write_on_this_camera,  # text
        position,  # position at which writing has to start
        cv2.FONT_HERSHEY_SIMPLEX,
        # font family (very limited selection, i think there's some interesting CV history
        # here...)
        0.5,  # font size
        (209, 180, 0, 255),  # font color
        1,
    )  # font stroke

    if full_charuco_detected_on_this_frame:
        cv2.polylines(
            image_w_markers, np.int32([charuco_corners]), False, (0, 100, 255), 2
        )
        # for these_corners in charuco_points_from_previous_frames:
        # if len(these_corners)>0:
        #     cv2.polylines(image_w_markers, np.int32([these_corners]), True, (0,100,255,
        #     255/2), 2)

    return True
