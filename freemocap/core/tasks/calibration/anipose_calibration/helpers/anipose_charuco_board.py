from abc import ABC, abstractmethod

import numpy as np
import cv2
from tqdm import trange

from freemocap.core.tasks.calibration.anipose_calibration.helpers.anipose_camera import AniposeCamera


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

class CalibrationObject(ABC):
    @abstractmethod
    def draw(self, size):
        pass

    @abstractmethod
    def detect_image(self, image):
        pass

    @abstractmethod
    def manually_verify_board_detection(self, image, corners):
        pass

    @abstractmethod
    def get_object_points(self):
        pass

    @abstractmethod
    def estimate_pose_points(self, camera, corners, ids):
        pass

    @abstractmethod
    def fill_points(self, corners, ids):
        pass

    @abstractmethod
    def get_empty_detection(self):
        pass

    def estimate_pose_image(self, camera, image):
        corners, ids = self.detect_image(image)
        return self.estimate_pose_points(camera, corners, ids)

    def detect_images(self, images, progress=False, prefix=None):
        length = len(images)
        rows = []

        if progress:
            it = trange(length, ncols=70)
        else:
            it = range(length)

        for framenum in it:
            imname = images[framenum]
            frame = cv2.imread(imname)

            corners, ids = self.detect_image(frame)

            if corners is not None:

                if prefix is None:
                    key = framenum
                else:
                    key = (prefix, framenum)

                row = {
                    'framenum': key,
                    'corners': corners,
                    'ids': ids,
                    'fname': imname
                }

                rows.append(row)

        rows = self.fill_points_rows(rows)

        return rows

    def detect_video(self, vidname, prefix=None, skip=20, progress=False):
        cap = cv2.VideoCapture(vidname)
        if not cap.isOpened():
            raise FileNotFoundError(f'missing video file "{vidname}"')
        length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if length < 10:
            length = int(1e9)
            progress = False
        rows = []

        go = int(skip / 2)

        if progress:
            it = trange(length, ncols=70)
        else:
            it = range(length)

        for framenum in it:
            ret, frame = cap.read()
            if not ret:
                break
            if framenum % skip != 0 and go <= 0:
                continue

            corners, ids = self.detect_image(frame)

            if corners is not None and len(corners) > 0:
                if prefix is None:
                    key = framenum
                else:
                    key = (prefix, framenum)
                go = int(skip / 2)
                row = {'framenum': key, 'corners': corners, 'ids': ids}
                rows.append(row)

            go = max(0, go - 1)

        cap.release()

        rows = self.fill_points_rows(rows)

        return rows

    def estimate_pose_rows(self, camera, rows):
        for row in rows:
            rvec, tvec = self.estimate_pose_points(camera,
                                                   row['corners'],
                                                   row['ids'])
            row['rvec'] = rvec
            row['tvec'] = tvec
        return rows

    def fill_points_rows(self, rows):
        for row in rows:
            row['filled'] = self.fill_points(row['corners'], row['ids'])
        return rows

    def get_all_calibration_points(self, rows, min_points=5):
        rows = self.fill_points_rows(rows)

        objpoints = self.get_object_points()
        objpoints = objpoints.reshape(-1, 3)

        all_obj = []
        all_img = []

        for row in rows:
            filled_test = row['filled'].reshape(-1, 2)
            good = np.all(~np.isnan(filled_test), axis=1)
            filled_app = row['filled'].reshape(-1, 2)
            objp = np.copy(objpoints)
            if np.sum(good) >= min_points:
                all_obj.append(np.float32(objp[good]))
                all_img.append(np.float32(filled_app[good]))

        # all_obj = np.vstack(all_obj)
        # all_img = np.vstack(all_img)

        # all_obj = np.array(all_obj, dtype='float64')
        # all_img = np.array(all_img, dtype='float64')

        return all_obj, all_img


class Checkerboard(CalibrationObject):
    DETECT_PARAMS = \
        cv2.CALIB_CB_NORMALIZE_IMAGE + \
        cv2.CALIB_CB_ADAPTIVE_THRESH + \
        cv2.CALIB_CB_FAST_CHECK

    SUBPIX_CRITERIA = (cv2.TERM_CRITERIA_EPS +
                       cv2.TERM_CRITERIA_MAX_ITER,
                       30, 0.01)

    def __init__(self, squaresX, squaresY, square_length=1, manually_verify=False):
        self.squaresX = squaresX
        self.squaresY = squaresY
        self.square_length = square_length
        self.manually_verify = manually_verify

        total_size = squaresX * squaresY

        objp = np.zeros((total_size, 3), np.float64)
        objp[:, :2] = np.mgrid[0:squaresX, 0:squaresY].T.reshape(-1, 2)
        objp *= square_length
        self.objPoints = objp

        self.ids = np.arange(total_size)

        self.empty_detection = np.zeros((total_size, 1, 2)) * np.nan

    def get_size(self):
        size = (self.squaresX, self.squaresY)
        return size

    def get_empty_detection(self):
        return np.copy(self.empty_detection)

    def get_square_length(self):
        return self.square_length

    # TODO: implement checkerboard draw function
    def draw(self, size):
        pass

    def get_empty(self):
        return np.copy(self.empty_detection)

    def fill_points(self, corners, ids=None):
        out = self.get_empty_detection()
        if corners is None or len(corners) == 0:
            return out
        if ids is None:
            return corners
        else:
            ids = ids.ravel()
            for i, cxs in zip(ids, corners):
                out[i] = cxs
            return out

    def detect_image(self, image, subpix=True):

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        size = self.get_size()
        pattern_was_found, corners = cv2.findChessboardCorners(gray, size, self.DETECT_PARAMS)

        if corners is not None:

            if subpix:
                corners = cv2.cornerSubPix(gray, corners, (3, 3), (-1, -1), self.SUBPIX_CRITERIA)

        if corners is not None \
            and self.manually_verify \
                and not self.manually_verify_board_detection(gray, corners):
            corners = None

        if corners is None:
            ids = None
        else:
            ids = self.ids

        return corners, ids

    def manually_verify_board_detection(self, image, corners):

        height, width = image.shape[:2]
        image = cv2.drawChessboardCorners(image, self.get_size(), corners, 1)
        cv2.putText(image, '(a) Accept (d) Reject', (int(width/1.35), int(height/16)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 1, cv2.LINE_AA)
        cv2.imshow('verify_detection', image)
        while 1:
            key = cv2.waitKey(0) & 0xFF
            if key == ord('a'):
                cv2.putText(image, 'Accepted!', (int(width/2.5), int(height/1.05)), cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2, cv2.LINE_AA)
                cv2.imshow('verify_detection', image)
                cv2.waitKey(100)
                return True
            elif key == ord('d'):
                cv2.putText(image, 'Rejected!', (int(width/2.5), int(height/1.05)), cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2, cv2.LINE_AA)
                cv2.imshow('verify_detection', image)
                cv2.waitKey(100)
                return False

    def get_object_points(self):
        return self.objPoints

    def estimate_pose_points(self, camera, points, ids=None):
        ngood = np.sum(~np.isnan(points)) // 2
        if points is None or ngood < 7:
            return None, None

        n_points = points.size // 2
        points = np.reshape(points, (n_points, 1, 2))

        K = camera.get_camera_matrix()
        D = camera.get_distortions()
        obj_points = self.get_object_points()

        if points.shape[0] != obj_points.shape[0]:
            return None, None

        try:
            retval, rvec, tvec, inliers = cv2.solvePnPRansac(obj_points,
                                                             points,
                                                             K,
                                                             D,
                                                             confidence=0.9,
                                                             reprojectionError=30)
            return rvec, tvec

        except:
            print("W: failed to find checkerboard pose in image")
            return None, None




class CharucoBoard(CalibrationObject):
    def __init__(self,
                 squaresX,
                 squaresY,
                 square_length,
                 marker_length,
                 marker_bits=4,
                 dict_size=50,
                 aruco_dict=None,
                 manually_verify=False):
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
            (7, 1000): cv2.aruco.DICT_7X7_1000
        }

        dkey = (marker_bits, dict_size)
        self.dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[dkey])

        self.board = cv2.aruco.CharucoBoard([squaresX, squaresY],
                                            square_length, marker_length,
                                            self.dictionary)

        total_size = (squaresX - 1) * (squaresY - 1)

        objp = np.zeros((total_size, 3), np.float64)
        objp[:, :2] = np.mgrid[0:(squaresX - 1), 0:(squaresY - 1)].T.reshape(
            -1, 2)
        objp *= square_length
        self.objPoints = objp

        self.empty_detection = np.zeros((total_size, 1, 2)) * np.nan
        self.total_size = total_size

    def get_size(self):
        size = (self.squaresX, self.squaresY)
        return size

    def get_square_length(self):
        return self.square_length

    def get_empty_detection(self):
        return np.copy(self.empty_detection)

    def draw(self, size):
        return self.board.draw(size)

    def fill_points(self, corners, ids):
        out = self.get_empty_detection()
        if corners is None or len(corners) == 0:
            return out
        ids = ids.ravel()
        for i, cxs in zip(ids, corners):
            out[i] = cxs
        return out

    def detect_markers(self, image, camera=None, refine=True):
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_CONTOUR
        params.adaptiveThreshWinSizeMin = 50
        params.adaptiveThreshWinSizeMax = 700
        params.adaptiveThreshWinSizeStep = 50
        params.adaptiveThreshConstant = 0

        try:
            corners, ids, rejectedImgPoints = cv2.aruco.detectMarkers(
                gray, self.dictionary, parameters=params)
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
            detectedCorners, detectedIds, rejectedCorners, recoveredIdxs = \
                cv2.aruco.refineDetectedMarkers(gray, self.board, corners, ids,
                                            rejectedImgPoints,
                                            K, D,
                                            parameters=params)
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
            ret, detectedCorners, detectedIds = cv2.aruco.interpolateCornersCharuco(
                corners, ids, gray, self.board)
            if detectedIds is None:
                detectedCorners = detectedIds = np.float64([])
        else:
            detectedCorners = detectedIds = np.float64([])

        if len(detectedCorners) > 0 \
            and self.manually_verify \
            and not self.manually_verify_board_detection(gray, detectedCorners, detectedIds):
            detectedCorners = detectedIds = np.float64([])

        return detectedCorners, detectedIds


    def manually_verify_board_detection(self, image, corners, ids=None):

        height, width = image.shape[:2]
        image = cv2.aruco.drawDetectedCornersCharuco(image, corners, ids)
        cv2.putText(image, '(a) Accept (d) Reject', (int(width/1.35), int(height/16)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 1, cv2.LINE_AA)
        cv2.imshow('verify_detection', image)
        while 1:
            key = cv2.waitKey(0) & 0xFF
            if key == ord('a'):
                cv2.putText(image, 'Accepted!', (int(width/2.5), int(height/1.05)), cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2, cv2.LINE_AA)
                cv2.imshow('verify_detection', image)
                cv2.waitKey(100)
                return True
            elif key == ord('d'):
                cv2.putText(image, 'Rejected!', (int(width/2.5), int(height/1.05)), cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2, cv2.LINE_AA)
                cv2.imshow('verify_detection', image)
                cv2.waitKey(100)
                return False

    def get_object_points(self):
        return self.objPoints

    def estimate_pose_points(self, camera, corners, ids):
        if corners is None or ids is None or len(corners) < 7:
            return None, None

        n_corners = corners.size // 2
        corners = np.reshape(corners, (n_corners, 1, 2))

        K = camera.get_camera_matrix()
        D = camera.get_distortions()

        ret, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(
            corners, ids, self.board, K, D, None, None)

        return rvec, tvec
class AniposeCharucoBoard(CharucoBoard):
    def __init__(
            self,
            squaresX: int = 5,
            squaresY: int = 7,
            square_length: float = 1.0,
            marker_length: float = 0.8,
            marker_bits: int = 4,
            dict_size: int = 250,
    ):
        super().__init__(squaresX, squaresY, square_length, marker_length, marker_bits, dict_size)
        self.squaresX = squaresX
        self.squaresY = squaresY
        self.square_length = square_length
        self.marker_length = marker_length
        self.marker_bits = marker_bits
        self.dict_size = dict_size

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
        objp[:, :2] = np.mgrid[0: (squaresX - 1), 0: (squaresY - 1)].T.reshape(-1, 2)
        objp *= square_length
        self.objPoints = objp
        self.empty_detection = np.zeros((total_size, 1, 2)) * np.nan
        self.total_size = total_size

    def detect_markers(self, image: np.ndarray, camera=None, refine: bool = True):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

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

        K = D = None
        if camera is not None:
            K = camera.get_camera_matrix()
            D = camera.get_distortions()

        if refine:
            detectedCorners, detectedIds, _, _ = cv2.aruco.refineDetectedMarkers(
                gray, self.board, corners, ids, rejectedImgPoints, K, D, parameters=params
            )
        else:
            detectedCorners, detectedIds = corners, ids

        return detectedCorners, detectedIds

    def detect_image(self, image: np.ndarray, camera=None):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        corners, ids = self.detect_markers(image, camera, refine=True)
        if len(corners) > 0:
            ret, detectedCorners, detectedIds = cv2.aruco.interpolateCornersCharuco(
                corners, ids, gray, self.board
            )
            if detectedIds is None:
                detectedCorners = detectedIds = np.float64([])
        else:
            detectedCorners = detectedIds = np.float64([])

        return detectedCorners, detectedIds

    def estimate_pose_points(
        self,
        camera: AniposeCamera,
        corners: np.ndarray | None,
        ids: np.ndarray | None,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Estimate board pose via solvePnP using detected charuco corner positions and their known 3D locations."""
        # cv2.solvePnP's DLT algorithm requires >= 6 point correspondences; skip frames below that.
        if corners is None or ids is None or len(corners) < 6:
            return None, None

        flat_ids = ids.flatten()
        obj_points = self.objPoints[flat_ids].astype(np.float64)
        img_points = corners.reshape(-1, 1, 2).astype(np.float64)

        K = camera.camera_matrix
        D = camera.distortion_coefficients

        ret, rvec, tvec = cv2.solvePnP(
            objectPoints=obj_points,
            imagePoints=img_points,
            cameraMatrix=K,
            distCoeffs=D,
        )
        if not ret:
            return None, None
        return rvec, tvec
