import cv2
import numpy as np

from freemocap.zzold.core_processes.capture_volume_calibration.anipose_camera_calibration.anipose_stuff import \
    Camera


class FisheyeCamera(Camera):
    def __init__(
        self,
        matrix=np.eye(3),
        dist=np.zeros(4),
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

    def from_dict(d):
        cam = FisheyeCamera()
        cam.load_dict(d)
        return cam

    def get_dict(self):
        d = super().get_dict()
        d["fisheye"] = True
        return d

    def distort_points(self, points):
        shape = points.shape
        points = points.reshape(-1, 1, 2)
        new_points = np.dstack([points, np.ones((points.shape[0], 1, 1))])
        out, _ = cv2.fisheye.projectPoints(
            new_points,
            np.zeros(3),
            np.zeros(3),
            self.matrix.astype("float64"),
            self.dist.astype("float64"),
        )
        return out.reshape(shape)

    def undistort_points(self, points):
        shape = points.shape
        points = points.reshape(-1, 1, 2)
        out = cv2.fisheye.undistortPoints(
            points.astype("float64"),
            self.matrix.astype("float64"),
            self.dist.astype("float64"),
        )
        return out.reshape(shape)

    def project(self, points):
        points = points.reshape(-1, 1, 3)
        out, _ = cv2.fisheye.projectPoints(
            points,
            self.rvec,
            self.tvec,
            self.matrix.astype("float64"),
            self.dist.astype("float64"),
        )
        return out

    def set_params(self, params):
        self.set_rotation(params[0:3])
        self.set_translation(params[3:6])
        self.set_focal_length(params[6])

        dist = np.zeros(4, dtype="float64")
        dist[0] = params[7]
        if self.extra_dist:
            dist[1] = params[8]
        # dist[2] = params[9]
        # dist[3] = params[10]
        self.set_distortions(dist)

    def get_params(self):
        params = np.zeros(8 + self.extra_dist, dtype="float64")
        params[0:3] = self.get_rotation()
        params[3:6] = self.get_translation()
        params[6] = self.get_focal_length()
        dist = self.get_distortions()
        params[7] = dist[0]
        if self.extra_dist:
            params[8] = dist[1]
        # params[9] = dist[2]
        # params[10] = dist[3]
        return params

    def copy(self):
        return FisheyeCamera(
            matrix=self.get_camera_matrix().copy(),
            dist=self.get_distortions().copy(),
            size=self.get_size(),
            rvec=self.get_rotation().copy(),
            tvec=self.get_translation().copy(),
            name=self.get_name(),
            extra_dist=self.extra_dist,
        )
