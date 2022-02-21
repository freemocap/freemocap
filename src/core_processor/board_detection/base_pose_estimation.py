import cv2

from src.core_processor.board_detection.charuco_constants import aruco_dict, board


def detect_charuco_board(image):
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
