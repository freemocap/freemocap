import logging
from pathlib import Path

import cv2
import numpy as np
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pubsub.pubsub_topics import CameraNodeOutputMessage
from freemocap.core.tasks.calibration_task.calibration_helpers.multi_camera_calibrator import MultiCameraCalibrator
from freemocap.core.tasks.calibration_task.point_triangulator import PointTriangulator, CameraCalibrationData

logger = logging.getLogger(__name__)


def create_triangulator_from_calibrator(
    multi_camera_calibrator: MultiCameraCalibrator
) -> PointTriangulator:
    """
    Convert MultiCameraCalibrator calibration results into PointTriangulator format.
    
    :param multi_camera_calibrator: Calibrated multi-camera system
    :return: Initialized PointTriangulator ready for fast triangulation
    :raises ValueError: If calibrator doesn't have calibration data
    """
    if not multi_camera_calibrator.has_calibration:
        raise ValueError(
            "MultiCameraCalibrator must be calibrated before creating triangulator. "
            "Call calibrate() first."
        )
    
    camera_calibrations: dict[str, CameraCalibrationData] = {}
    
    for camera_id, single_camera_calibrator in multi_camera_calibrator.single_camera_calibrators.items():
        # Get intrinsics from single camera calibrator
        intrinsics = single_camera_calibrator.camera_intrinsics_estimate
        camera_matrix = intrinsics.camera_matrix
        distortion_coeffs = intrinsics.distortion_coefficients
        
        # Get extrinsics from multi-camera calibration estimate
        transform = multi_camera_calibrator.multi_camera_calibration_estimate.camera_transforms_by_camera_id[camera_id]
        extrinsics = transform.extrinsics_matrix
        
        # Extract rotation vector and translation from extrinsics matrix [R|t]
        rotation_matrix = extrinsics[:3, :3]
        translation_vector = extrinsics[:3, 3]
        rotation_vector = cv2.Rodrigues(rotation_matrix)[0].ravel()
        
        # Get image size
        image_size = single_camera_calibrator.image_size
        
        # Create CameraCalibrationData
        camera_calibrations[camera_id] = CameraCalibrationData(
            name=camera_id,
            image_size=image_size,
            matrix=camera_matrix,
            distortion=distortion_coeffs,
            rotation_vector=rotation_vector,
            translation=translation_vector
        )
    
    return PointTriangulator(camera_calibrations=camera_calibrations)


def triangulate_list(
    triangulator: PointTriangulator,
    camera_node_outputs_stream: list[dict[CameraIdString, CameraNodeOutputMessage]],
    undistort_points: bool = True,
    compute_reprojection_error: bool = False
) -> tuple[np.ndarray, np.ndarray | None]:
    """
    Efficiently triangulate a stream of multi-camera observations.
    
    :param triangulator: Initialized PointTriangulator
    :param camera_node_outputs_stream: List of frame observations across cameras
    :param undistort_points: Whether to undistort points before triangulation
    :param compute_reprojection_error: Whether to compute reprojection errors
    :return: Tuple of (all_points3d, all_errors)
             - all_points3d: Shape (F, M, 3) - F frames, M charuco corners, 3D coords
             - all_errors: Shape (F, M) - reprojection errors per point per frame, or None
    :raises ValueError: If stream is empty or cameras missing
    """
    if not camera_node_outputs_stream:
        raise ValueError("camera_node_outputs_stream cannot be empty")
    
    num_frames = len(camera_node_outputs_stream)
    
    # Get number of charuco corners from first valid observation
    first_frame = camera_node_outputs_stream[0]
    first_camera_output = next(iter(first_frame.values()))
    num_corners = first_camera_output.charuco_observation.to_2d_array().shape[0]
    
    # Pre-allocate output arrays
    all_points3d = np.empty((num_frames, num_corners, 3), dtype=np.float64)
    all_errors = np.empty((num_frames, num_corners), dtype=np.float64) if compute_reprojection_error else None
    
    # Process each frame
    for frame_idx, camera_node_outputs in enumerate(camera_node_outputs_stream):
        try:
            points3d, errors = triangulator.triangulate_camera_node_outputs(
                camera_node_outputs=camera_node_outputs,
                undistort_points=undistort_points,
                compute_reprojection_error=compute_reprojection_error
            )
            
            all_points3d[frame_idx] = points3d
            if compute_reprojection_error and errors is not None:
                all_errors[frame_idx] = errors
                
        except ValueError as e:
            logger.error(f"Triangulation failed for frame {frame_idx}: {e}")
            raise
    
    return all_points3d, all_errors


