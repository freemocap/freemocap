import cv2
import numpy as np
from aniposelib.utils import make_M


class AniposeCamera:
    def __init__(
        self,
        matrix=np.eye(3),
        dist=np.zeros(5),
        size=None,
        rvec=np.zeros(3),
        tvec=np.zeros(3),
        name=None,
        extra_dist=False,
    ):
        self.set_camera_matrix(matrix)
        self.set_distortions(dist)
        self.set_size(size)
        self.set_rotation(rvec)
        self.set_translation(tvec)
        self.set_name(name)
        self.extra_dist = extra_dist

    def get_dict(self):
        return {
            "name": self.get_name(),
            "size": list(self.get_size()),
            "matrix": self.get_camera_matrix().tolist(),
            "distortions": self.get_distortions().tolist(),
            "rotation": self.get_rotation().tolist(),
            "translation": self.get_translation().tolist(),
        }

    def load_dict(self, d):
        self.set_camera_matrix(d["matrix"])
        self.set_rotation(d["rotation"])
        self.set_translation(d["translation"])
        self.set_distortions(d["distortions"])
        self.set_name(d["name"])
        self.set_size(d["size"])

    def from_dict(d):
        cam = Camera()
        cam.load_dict(d)
        return cam

    def get_camera_matrix(self):
        return self.camera_matrix

    def get_distortions(self):
        return self.distortion_coefficients

    def set_camera_matrix(self, matrix):
        self.camera_matrix = np.array(matrix, dtype="float64")

    def set_focal_length(self, fx, fy=None):
        if fy is None:
            fy = fx
        self.camera_matrix[0, 0] = fx
        self.camera_matrix[1, 1] = fy

    def get_focal_length(self, both=False):
        fx = self.camera_matrix[0, 0]
        fy = self.camera_matrix[1, 1]
        if both:
            return (fx, fy)
        else:
            return (fx + fy) / 2.0

    def set_distortions(self, dist):
        self.distortion_coefficients = np.array(dist, dtype="float64").ravel()

    def set_rotation(self, rvec):
        self.rotation_vector = np.array(rvec, dtype="float64").ravel()

    def get_rotation(self):
        return self.rotation_vector

    def set_translation(self, tvec):
        self.translation_vector = np.array(tvec, dtype="float64").ravel()

    def get_translation(self):
        return self.translation_vector

    def get_extrinsics_mat(self):
        return make_M(self.rotation_vector, self.translation_vector)

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = str(name)

    def set_size(self, size):
        """set size as (width, height)"""
        self.size = size

    def get_size(self):
        """get size as (width, height)"""
        return self.size

    def resize_camera(self, scale):
        """resize the camera by scale factor, updating intrinsics to match"""
        size = self.get_size()
        new_size = size[0] * scale, size[1] * scale
        matrix = self.get_camera_matrix()
        new_matrix = matrix * scale
        new_matrix[2, 2] = 1
        self.set_size(new_size)
        self.set_camera_matrix(new_matrix)

    def get_params(self):
        params = np.zeros(8 + self.extra_dist, dtype="float64")
        params[0:3] = self.get_rotation()
        params[3:6] = self.get_translation()
        params[6] = self.get_focal_length()
        dist = self.get_distortions()
        params[7] = dist[0]
        if self.extra_dist:
            params[8] = dist[1]
        return params

    def set_params(self, params):
        self.set_rotation(params[0:3])
        self.set_translation(params[3:6])
        self.set_focal_length(params[6])

        dist = np.zeros(5, dtype="float64")
        dist[0] = params[7]
        if self.extra_dist:
            dist[1] = params[8]
        self.set_distortions(dist)


    def undistort_points(self, points):
        shape = points.shape
        points = points.reshape(-1, 1, 2)
        out = cv2.undistortPoints(points, self.camera_matrix.astype("float64"), self.distortion_coefficients.astype("float64"))
        return out.reshape(shape)

    def project_3d_to_2d(self, points3d:np.ndarray) -> np.ndarray:
        if not points3d.shape[-1] == 3:
            raise ValueError("points3d must have shape (N, 3)")
        points3d = points3d.reshape(-1, 1, 3)
        projected_2d_points, _ = cv2.projectPoints(
            points3d,
            self.rotation_vector,
            self.translation_vector,
            self.camera_matrix.astype("float64"),
            self.distortion_coefficients.astype("float64"),
        )
        if projected_2d_points.shape != (points3d.shape[0], 1, 2):
            raise ValueError(f"projected_2d_points has incorrect shape: {projected_2d_points.shape}")

        return projected_2d_points

    def single_camera_reprojection_error(self, p3d, p2d):
        projecting_3d_points_onto_2d_image_plane_og = self.project(p3d)
        projecting_3d_points_onto_2d_image_plane = projecting_3d_points_onto_2d_image_plane_og.reshape(p2d.shape)
        return p2d - projecting_3d_points_onto_2d_image_plane

