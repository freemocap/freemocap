import cv2
import numpy as np
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.calibration_task.calibration_helpers.calibration_numpy_types import ObjectPoint3D, \
    ImagePoints2D, ObjectPoints3D, ReprojectionError, CameraExtrinsicsMatrix, ImagePoint2D
from freemocap.core.tasks.calibration_task.calibration_helpers.camera_math_models import TransformationMatrix
from freemocap.core.tasks.calibration_task.calibration_helpers.single_camera_calibrator import \
    CameraIntrinsicsEstimate


def undistort_points(points2d: ImagePoints2D,
                     camera_intrinsics: CameraIntrinsicsEstimate) -> ImagePoints2D:
    """
    Undistorts 2D points using the camera's intrinsic parameters and distortion coefficients.

    This function adjusts the provided 2D points to account for lens distortion, returning
    points that are mapped as they would appear in an ideal pinhole camera model. The process
    ensures (or attempts to ensure) that the ray passing from the nodal point of the camera lens through the
    undistorted 2D point intersects the corresponding 3D point in space accurately.

    :param points2d: A NumPy array of shape (N, 2) representing the 2D points
                     to be undistorted, where N is the number of 2d points. These are typically the distorted
                     pixel coordinates captured by the camera.
    :return: A NumPy array of the same shape as `points2d` containing the undistorted 2D points (in normalized image coordinates, I think?).
    """
    undistorted_points2d = cv2.undistortPoints(src=points2d,
                                               cameraMatrix= camera_intrinsics.camera_matrix.matrix,
                                               distCoeffs=camera_intrinsics.distortion_coefficients.coefficients,
                                               )

    return np.squeeze(undistorted_points2d)


# @jit(nopython=True, parallel=False)
def triangulate_point(image_point_by_camera: dict[CameraIdString, ImagePoint2D],
                       camera_extrinsics: dict[CameraIdString, CameraExtrinsicsMatrix]) -> ObjectPoint3D:
    _validate_triangulation_input(camera_extrinsics=camera_extrinsics,
                                  image_point_by_camera=image_point_by_camera)
    camera_ids = list(camera_extrinsics.keys())
    number_of_cameras = len(camera_ids)
    A = np.zeros((number_of_cameras * 2, 4)) #SVD needs this to be a 2d array of shape (2n, 4), where n is the number of cameras
    for camera_number, camera_id in enumerate(camera_ids):
        image_points_x = image_point_by_camera[camera_id][0]
        image_points_y = image_point_by_camera[camera_id][1]
        camera_matrix = camera_extrinsics[camera_id]
        A[(camera_number * 2): (camera_number * 2 + 1)] = image_points_x * camera_matrix[2] - camera_matrix[0]
        A[(camera_number * 2 + 1): (camera_number * 2 + 2)] = image_points_y * camera_matrix[2] - camera_matrix[1]
    u, s, vh = np.linalg.svd(A, full_matrices=True) #SVD returns the singular values in descending order, so the last row of vh is the solution (i.e. the 3D point represented in homogeneous coordinates)
    points_3d = vh[-1]
    points_3d = points_3d[:3] / points_3d[3]
    return points_3d


def _validate_triangulation_input(camera_extrinsics: dict[CameraIdString, CameraExtrinsicsMatrix],
                                  image_point_by_camera: dict[CameraIdString, ImagePoint2D]):
    if len(image_point_by_camera) < 2:
        raise ValueError("Need at least two cameras to triangulate points.")
    if image_point_by_camera.keys() != camera_extrinsics.keys():
        raise ValueError("Camera IDs in image_point_by_camera and camera_extrinsics must match.")
    if not all([image_point_by_camera[camera_id].shape == (2,) for camera_id in image_point_by_camera.keys()]):
        raise ValueError("All image points must be 2D points.")
    if not all([camera_extrinsics[camera_id].shape == (3, 4)for camera_id in camera_extrinsics.keys()]):
        raise ValueError("All camera extrinsics must be 3x4 matrices.")


def _validate_reprojection_error_input(object_points: ObjectPoints3D,
                                        image_points_by_camera: dict[CameraIdString, ImagePoints2D],
                                        camera_intrinsics: dict[CameraIdString, CameraIntrinsicsEstimate],
                                        camera_transforms: dict[CameraIdString, TransformationMatrix],
                                        image_sizes: dict[CameraIdString, tuple[int, int]]):
    if len(image_points_by_camera) < 2:
        raise ValueError("Need at least two cameras to triangulate points.")
    if any([image_sizes.keys() != camera_intrinsics.keys(),
            image_sizes.keys() != camera_transforms.keys(),
            image_sizes.keys() != image_points_by_camera.keys()]):
        raise ValueError("Camera IDs in image_points_by_camera, camera_intrinsics, and camera_transforms must match.")
    for camera_id in image_points_by_camera.keys():
        if not all ([point.shape == (2,) for point in image_points_by_camera[camera_id]]):
            raise ValueError("All image points must be 2D points.")



# @jit(nopython=True, parallel=False)
def calculate_reprojection_error(object_points: ObjectPoints3D,
                                 image_points_by_camera: dict[CameraIdString, ImagePoints2D],
                                 camera_intrinsics: dict[CameraIdString, CameraIntrinsicsEstimate],
                                 camera_transforms: dict[CameraIdString, TransformationMatrix],
                                 image_sizes: dict[CameraIdString, tuple[int, int]]) -> tuple[list[ReprojectionError], dict[CameraIdString, list[ReprojectionError]]]:
    # https://docs.opencv.org/4.10.0/d9/d0c/group__calib3d.html#ga1019495a2c8d1743ed5cc23fa0daff8c
    _validate_reprojection_error_input(object_points=object_points,
                                        image_points_by_camera=image_points_by_camera,
                                        camera_intrinsics=camera_intrinsics,
                                        camera_transforms=camera_transforms,
                                        image_sizes=image_sizes)
    reprojection_error_per_point_by_camera: dict[CameraIdString, list[ReprojectionError]] = {}
    for camera_id in camera_intrinsics.keys():
        projected_image_points, jacobian = cv2.projectPoints(objectPoints=object_points,
                                                             rvec=camera_transforms[camera_id].rotation_vector.vector,
                                                             tvec=camera_transforms[
                                                                 camera_id].translation_vector.vector,
                                                             cameraMatrix=camera_intrinsics[
                                                                 camera_id].camera_matrix.matrix,
                                                             distCoeffs=camera_intrinsics[
                                                                 camera_id].distortion_coefficients.coefficients,
                                                             aspectRatio=image_sizes[camera_id][0] / image_sizes[camera_id][1]
                                                             )

        reprojection_error_per_point_by_camera[camera_id]= np.abs(image_points_by_camera[camera_id] - np.squeeze(projected_image_points))

    mean_reprojection_error_per_point = []
    for point_index in range(len(object_points)):
        point_reprojection_error = []
        for camera_id in camera_intrinsics.keys():
            point_reprojection_error.append(reprojection_error_per_point_by_camera[camera_id][point_index])
        mean_reprojection_error_per_point.append(float(np.nanmean(point_reprojection_error)))

    return mean_reprojection_error_per_point, reprojection_error_per_point_by_camera
