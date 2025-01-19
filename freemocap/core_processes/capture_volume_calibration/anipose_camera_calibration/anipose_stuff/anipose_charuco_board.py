import cv2
import numpy as np
from aniposelib.boards import CharucoBoard


class AniposeCharucoBoard(CharucoBoard):
    def __init__(
        self,
        squaresX,
        squaresY,
        square_length,
        marker_length,
        marker_bits=4,
        dict_size=50,
        aruco_dict=None,
        manually_verify=False,
    ):
        self.squaresX = squaresX
        self.squaresY = squaresY
        self.square_length = square_length
        self.marker_length = marker_length
        self.manually_verify = manually_verify

        ARUCO_DICTS = {
            (4, 50): cv2.aruco.DICT_4X4_50,
            (5, 50): cv2.aruco.DICT_5X5_50,
            (6, 50): cv2.aruco.DICT_6X6_50,
            (7, 50): cv2.aruco.DICT_7X7_50,
            (4, 100): cv2.aruco.DICT_4X4_100,
            (5, 100): cv2.aruco.DICT_5X5_100,
            (6, 100): cv2.aruco.DICT_6X6_100,
            (7, 100): cv2.aruco.DICT_7X7_100,
            (4, 250): cv2.aruco.DICT_4X4_250,
            (5, 250): cv2.aruco.DICT_5X5_250,
            (6, 250): cv2.aruco.DICT_6X6_250,
            (7, 250): cv2.aruco.DICT_7X7_250,
            (4, 1000): cv2.aruco.DICT_4X4_1000,
            (5, 1000): cv2.aruco.DICT_5X5_1000,
            (6, 1000): cv2.aruco.DICT_6X6_1000,
            (7, 1000): cv2.aruco.DICT_7X7_1000,
        }

        dkey = (marker_bits, dict_size)
        self.dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[dkey])

        self.board = cv2.aruco.CharucoBoard(
            size=[squaresX, squaresY],
            squareLength=square_length,
            markerLength=marker_length,
            dictionary=self.dictionary,
        )

        total_size = (squaresX - 1) * (squaresY - 1)

        objp = np.zeros((total_size, 3), np.float64)
        objp[:, :2] = np.mgrid[0 : (squaresX - 1), 0 : (squaresY - 1)].T.reshape(-1, 2)
        objp *= square_length
        self.objPoints = objp

        self.empty_detection = np.zeros((total_size, 1, 2)) * np.nan
        self.total_size = total_size

    def detect_markers(self, image, camera=None, refine=True):
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_CONTOUR
        params.adaptiveThreshWinSizeMin = 100
        params.adaptiveThreshWinSizeMax = 700
        params.adaptiveThreshWinSizeStep = 50
        params.adaptiveThreshConstant = 0

        try:
            corners, ids, rejectedImgPoints = cv2.aruco.detectMarkers(gray, self.dictionary, parameters=params)
        except Exception:
            ids = None

        if ids is None:
            return [], []

        if camera is None:
            K = D = None
        else:
            K = camera.get_camera_matrix()
            D = camera.get_distortions()

        if refine:
            detectedCorners, detectedIds, rejectedCorners, recoveredIdxs = cv2.aruco.refineDetectedMarkers(
                gray, self.board, corners, ids, rejectedImgPoints, K, D, parameters=params
            )
        else:
            detectedCorners, detectedIds = corners, ids

        return detectedCorners, detectedIds

    def detect_image(self, image, camera=None):
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        corners, ids = self.detect_markers(image, camera, refine=True)
        if len(corners) > 0:
            ret, detectedCorners, detectedIds = cv2.aruco.interpolateCornersCharuco(corners, ids, gray, self.board)
            if detectedIds is None:
                detectedCorners = detectedIds = np.float64([])
        else:
            detectedCorners = detectedIds = np.float64([])

        if (
            len(detectedCorners) > 0
            and self.manually_verify
            and not self.manually_verify_board_detection(gray, detectedCorners, detectedIds)
        ):
            detectedCorners = detectedIds = np.float64([])

        return detectedCorners, detectedIds

    def manually_verify_board_detection(self, image, corners, ids=None):
        height, width = image.shape[:2]
        image = cv2.aruco.drawDetectedCornersCharuco(image, corners, ids)
        cv2.putText(
            image,
            "(a) Accept (d) Reject",
            (int(width / 1.35), int(height / 16)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            255,
            1,
            cv2.LINE_AA,
        )
        cv2.imshow("verify_detection", image)
        while 1:
            key = cv2.waitKey(0) & 0xFF
            if key == ord("a"):
                cv2.putText(
                    image,
                    "Accepted!",
                    (int(width / 2.5), int(height / 1.05)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    255,
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow("verify_detection", image)
                cv2.waitKey(100)
                return True
            elif key == ord("d"):
                cv2.putText(
                    image,
                    "Rejected!",
                    (int(width / 2.5), int(height / 1.05)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    255,
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow("verify_detection", image)
                cv2.waitKey(100)
                return False

    def estimate_pose_points(self, camera, corners, ids):
        if corners is None or ids is None or len(corners) < 5:
            return None, None

        n_corners = corners.size // 2
        corners = np.reshape(corners, (n_corners, 1, 2))

        K = camera.get_camera_matrix()
        D = camera.get_distortions()

        ret, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(corners, ids, self.board, K, D, None, None)

        return rvec, tvec
