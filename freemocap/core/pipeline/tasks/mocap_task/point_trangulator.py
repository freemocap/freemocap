from dataclasses import dataclass

import cv2
import numpy as np
import toml
from freemocap.system.paths_and_filenames.path_getters import get_last_successful_calibration_toml_path
from skellycam import CameraId

MINIUMUM_CAMERAS_FOR_TRIANGULATION = 2

@dataclass
class CameraCalibrationData:
    name: str
    size: tuple[int, int]
    matrix: np.ndarray # 3x3•
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
        if self.rotation_vector is None:
            return np.eye(3)
        return cv2.Rodrigues(self.rotation_vector)[0]

    @property
    def extrinsics_matrix(self):
        extrinsics_matrix = np.zeros((3, 4))
        extrinsics_matrix[:, :3] = self.rotation_matrix
        extrinsics_matrix[:, 3] = self.translation
        if extrinsics_matrix.shape != (3, 4):
            raise ValueError(f"Expected extrinsic matrix to be of shape (3, 4), got {extrinsics_matrix.shape}")
        return extrinsics_matrix

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
        calibration_data.pop("metadata")
        #hacky use of enumerate to get camera id from (old style anipose) camera names
        camera_calibrations = {CameraId(camera_id): CameraCalibrationData.from_tuple(data) for camera_id, data in enumerate(calibration_data.items()) if camera_id != "metadata"}
        return cls(camera_calibrations=camera_calibrations)

    @property
    def camera_calibrations_array(self) -> np.ndarray:
        array =  np.array([calibration.extrinsics_matrix for calibration in self.camera_calibrations.values()])
        if not array.shape == (len(self.camera_calibrations), 3, 4):
            raise ValueError(f"Expected extrinsics matrix to be of shape (num_cams, 3, 4), got {array.shape}")
        return array

    def triangulate(self, points2d_by_camera: dict[CameraId, dict[str, tuple]], scale_by: float) -> dict[str, tuple]:
        all_camera_extrinsics_matrix = self.camera_calibrations_array.copy()
        point_names: list[str] = []
        points3d: dict[str, tuple] = {name: (np.isnan, np.isnan, np.isnan) for name in point_names}

        for camera_id, points2d in points2d_by_camera.items():
            if not point_names:
                point_names = list(points2d.keys())
                continue
            if point_names != list(points2d.keys()):
                raise ValueError(f"Expected point names to match, got {point_names} and {list(points2d.keys())}")

        for point_name in point_names:
            point2d_views = [points2d[point_name] for points2d in points2d_by_camera.values()]
            good_camera_matrices = []
            good_points2d_views = []

            for index, point2d in enumerate(point2d_views):
                if np.isnan(point2d).any():
                    continue
                good_camera_matrices.append(all_camera_extrinsics_matrix[index])
                good_points2d_views.append(point2d)

            if len(good_points2d_views) < MINIUMUM_CAMERAS_FOR_TRIANGULATION:
                continue
            good_point2d_views_array = np.array(good_points2d_views)
            good_camera_extrinsics_matrix = np.array(good_camera_matrices)
            _validate_input(good_point2d_views_array, good_camera_extrinsics_matrix)
            points3d[point_name] = triangulate_simple(good_point2d_views_array, good_camera_extrinsics_matrix)
            points3d[point_name] = tuple([point * scale_by for point in points3d[point_name]])

        return points3d

def _validate_input(points2d_by_camera: np.ndarray, camera_extrinsic_matricies:  np.ndarray):
    number_of_cameras, points_dimensions = points2d_by_camera.shape
    if points_dimensions != 2:
        raise ValueError(f"Expected points to be of shape (num_cams, 2), got {points2d_by_camera.shape}")
    if number_of_cameras != camera_extrinsic_matricies.shape[0]:
        raise ValueError(f"Expected number of cameras to match, got {number_of_cameras} and {camera_extrinsic_matricies.shape[0]}")
    if camera_extrinsic_matricies.shape[1:] != (3, 4):
        raise ValueError(f"Expected camera extrinsic matricies to be of shape (num_cams, 3, 4), got {camera_extrinsic_matricies.shape}")

# # @jit(nopython=True, parallel=False)
# def triangulate_simple(points2d_by_camera: np.ndarray, camera_extrinsic_matricies:  np.ndarray) -> tuple:
#     number_of_cameras, points_dimensions = points2d_by_camera.shape
#     _validate_input(points2d_by_camera, camera_extrinsic_matricies)
#     A = np.zeros((number_of_cameras * 2, 4))
#     for camera_number in range(number_of_cameras):
#         x, y = points2d_by_camera[camera_number]
#         camera_matrix = camera_extrinsic_matricies[camera_number]
#         A[(camera_number * 2) : (camera_number * 2 + 1)] = x * camera_matrix[2] - camera_matrix[0]
#         A[(camera_number * 2 + 1) : (camera_number * 2 + 2)] = y * camera_matrix[2] - camera_matrix[1]
#     u, s, vh = np.linalg.svd(A, full_matrices=True)
#     points_3d = vh[-1]
#     points_3d = points_3d[:3] / points_3d[3]
#     return tuple(points_3d)

if __name__ == "__main__":
    _point_triangulator = PointTriangulator.create()
    _points2d_by_camera = np.array([[1, 2], [3, 4], [5, 6]])
    _camera_extrinsic_matricies = np.array([[[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]], [[13, 14, 15, 16], [17, 18, 19, 20], [21, 22, 23, 24]], [[25, 26, 27, 28], [29, 30, 31, 32], [33, 34, 35, 36]]])
    triangulate_simple(_points2d_by_camera, _camera_extrinsic_matricies)
    _point_triangulator.triangulate()