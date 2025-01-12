from dataclasses import field, dataclass
import cv2
import numpy as np

import toml
from freemocap.pipelines.mocap_pipeline.mocap_camera_node import MocapCameraNode, MocapCameraNodeOutputData
from freemocap.system.paths_and_filenames.path_getters import get_last_successful_calibration_toml_path
from numba import jit
from skellycam import  CameraId
from skellytracker.trackers.mediapipe_tracker import MediapipeObservation

@dataclass
class CameraCalibrationData:
    name: str
    size: tuple[int, int]
    matrix: np.ndarray # 3x3
    distortion: np.ndarray # 1x5
    rotation_vector: np.ndarray # 3x1 rodriques rotation vector
    translation: np.ndarray # 3x1 XYZ translation vector

    @classmethod
    def from_tuple(cls, data: tuple):
        camera_id, data = data
        matrix = np.array(data["matrix"])
        distortion = np.array(data["distortions"])
        rotation_vector = np.array(data["rotation"])
        translation = np.array(data["translation"])
        return cls(
            name=camera_id,
            size=data["size"],
            matrix=matrix,
            distortion=distortion,
            rotation_vector=rotation_vector,
            translation=translation,
        )

    def __post_init__(self):
        if self.matrix.shape != (3, 3):
            raise ValueError(f"Expected matrix to be of shape (3, 3), got {self.matrix.shape}")
        if self.distortion.shape != ( 5,):
            raise ValueError(f"Expected distortion to be of shape (1, 5), got {self.distortion.shape}")
        if self.rotation_vector.shape != (3,):
            raise ValueError(f"Expected rotation vector to be of shape (3, 1), got {self.rotation_vector.shape}")
        if self.translation.shape != (3, ):
            raise ValueError(f"Expected translation to be of shape (3, 1), got {self.translation.shape}")

    @property
    def rotation_matrix(self):
        return cv2.Rodrigues(self.rotation_vector)[0]

    @property
    def extrinsics_matrix(self):
        m =  np.hstack((self.rotation_matrix, self.translation))
        if m.shape != (3, 4):
            raise ValueError(f"Expected extrinsic matrix to be of shape (3, 4), got {m.shape}")
        return m

    def undistort_2d_points(self, points: np.ndarray):
        shape = points.shape
        points = points.reshape(-1, 1, 2)
        out = cv2.undistortPoints(points, self.matrix.astype("float64"), self.distortion.astype("float64"))
        return out.reshape(shape)

    def project_3d_to_2d(self, points):
        points = points.reshape(-1, 1, 3)
        projected_points_2d, _ = cv2.projectPoints(
            points,
            self.rotation_vector,
            self.translation,
            self.matrix,
            self.distortion
        )
        projected_points_2d = np.squeeze(projected_points_2d)
        if projected_points_2d.shape[1] != 2:
            raise ValueError(f"Expected projected points to be of shape (n, 2), got {projected_points_2d.shape}")
        return projected_points_2d

@dataclass
class PointTriangulator:
    camera_calibrations: dict[CameraId, CameraCalibrationData]
    @classmethod
    def create(cls):
        calibration_toml_path = get_last_successful_calibration_toml_path()
        calibration_data = toml.load(calibration_toml_path)
        #hacky use of enumerate to get camera id from (old style anipose) camera names
        camera_calibrations = {CameraId(camera_id): CameraCalibrationData.from_tuple(data) for camera_id, data in enumerate(calibration_data.items()) if camera_id != "metadata"}
        return cls(camera_calibrations=camera_calibrations)

    def triangulate(self, observations_by_camera: dict[CameraId, MediapipeObservation]):
        f=9


@jit(nopython=True, parallel=False)
def triangulate_simple(points2d_by_camera: dict[CameraId, np.ndarray], camera_extrinsic_matricies: dict[CameraId, np.ndarray]):
    number_of_cameras = len(points2d_by_camera)
    A = np.zeros((number_of_cameras * 2, 4))
    for camera_number, points_2d, camera_matrix in enumerate(zip(points2d_by_camera.values(), camera_extrinsic_matricies.values())):
        x, y = points_2d
        A[(camera_number * 2) : (camera_number * 2 + 1)] = x * camera_matrix[2] - camera_matrix[0]
        A[(camera_number * 2 + 1) : (camera_number * 2 + 2)] = y * camera_matrix[2] - camera_matrix[1]
    u, s, vh = np.linalg.svd(A, full_matrices=True)
    points_3d = vh[-1]
    points_3d = points_3d[:3] / points_3d[3]
    return points_3d

if __name__ == "__main__":
    point_triangulator = PointTriangulator.create()
    points2d_by_camera = {CameraId(0): np.array([[1, 2], [3, 4]]), CameraId(1): np.array([[5, 6], [7, 8]])}
    camera_extrinsic_matricies = {CameraId(0): np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]), CameraId(1): np.array([[10, 11, 12], [13, 14, 15], [16, 17, 18]])}
    triangulate_simple(points2d_by_camera, camera_extrinsic_matricies)