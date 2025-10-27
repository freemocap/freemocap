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


def example_usage_calibration_to_triangulation():
    """Example showing complete workflow from calibration to triangulation."""
    
    # Step 1: Create multi-camera calibrator
    camera_ids = ["camera_0", "camera_1", "camera_2"]
    multi_camera_calibrator = MultiCameraCalibrator.from_camera_ids(
        camera_ids=camera_ids,
        principal_camera_id="camera_0"
    )
    
    # Step 2: Feed calibration frames
    # (In real usage, you'd accumulate frames in a loop)
    # for multi_frame_number, camera_outputs in enumerate(calibration_stream):
    #     multi_camera_calibrator.receive_camera_node_output(
    #         multi_frame_number=multi_frame_number,
    #         camera_node_output_by_camera=camera_outputs
    #     )
    
    # Step 3: Calibrate once enough shared views are collected
    if multi_camera_calibrator.ready_to_calibrate:
        calibration_estimate = multi_camera_calibrator.calibrate()
        logger.info("Initial calibration complete")
        
        # Optional: Refine with bundle adjustment
        # refined_estimate = multi_camera_calibrator.run_bundle_adjustment()
    else:
        raise ValueError("Not enough shared views for calibration")
    
    # Step 4: Create triangulator from calibration
    triangulator = create_triangulator_from_calibrator(multi_camera_calibrator)
    logger.info("Triangulator created from calibration")
    
    # Step 5: Fast triangulation loop for recording
    recorded_frames: list[dict[CameraIdString, CameraNodeOutputMessage]] = []
    
    # In real usage, this would be your recording loop:
    # while recording:
    #     camera_outputs = get_current_frame_from_cameras()
    #     recorded_frames.append(camera_outputs)
    
    # Step 6: Batch triangulate all recorded frames
    if recorded_frames:
        all_points3d, all_errors = triangulate_list(
            triangulator=triangulator,
            camera_node_outputs_stream=recorded_frames,
            undistort_points=True,
            compute_reprojection_error=True
        )
        
        logger.info(f"Triangulated {all_points3d.shape[0]} frames")
        logger.info(f"Points shape: {all_points3d.shape}")
        
        if all_errors is not None:
            mean_error = np.nanmean(all_errors)
            logger.info(f"Mean reprojection error: {mean_error:.2f} pixels")
        
        return all_points3d, all_errors
    
    return None, None


def example_usage_realtime_triangulation():
    """Example showing real-time triangulation during recording."""
    
    # Assume calibrator is already calibrated
    multi_camera_calibrator: MultiCameraCalibrator = load_calibrated_system()
    
    # Create triangulator once
    triangulator = create_triangulator_from_calibrator(multi_camera_calibrator)
    
    # Real-time triangulation loop
    points3d_buffer: list[np.ndarray] = []
    
    while recording_active():
        # Get current frame from all cameras
        camera_outputs = get_current_frame_from_cameras()
        
        # Triangulate immediately (very fast - typically <1ms)
        try:
            points3d, errors = triangulator.triangulate_camera_node_outputs(
                camera_node_outputs=camera_outputs,
                undistort_points=True,
                compute_reprojection_error=False  # Disable for max speed
            )
            
            points3d_buffer.append(points3d)
            
        except ValueError as e:
            logger.warning(f"Frame triangulation failed: {e}")
            # Continue recording even if one frame fails
            continue
    
    # Convert to array after recording
    all_points3d = np.array(points3d_buffer)
    return all_points3d


def save_triangulator_to_toml(
    triangulator: PointTriangulator,
    output_path: str | Path
) -> None:
    """
    Save triangulator calibration data to TOML file for later use.
    
    :param triangulator: Calibrated PointTriangulator
    :param output_path: Path to save TOML file
    """
    import toml
    
    output_path = Path(output_path)
    
    calibration_dict: dict[str, dict] = {
        "metadata": {
            "num_cameras": triangulator.num_cameras,
            "camera_names": triangulator.camera_names
        }
    }
    
    for camera_name, camera_calib in triangulator.camera_calibrations.items():
        calibration_dict[camera_name] = {
            "image_size": list(camera_calib.image_size),
            "matrix": camera_calib.matrix.tolist(),
            "distortions": camera_calib.distortion.tolist(),
            "rotation": camera_calib.rotation_vector.tolist(),
            "translation": camera_calib.translation.tolist()
        }
    
    with open(output_path, 'w') as f:
        toml.dump(calibration_dict, f)
    
    logger.info(f"Triangulator calibration saved to {output_path}")


def load_calibrated_system() -> MultiCameraCalibrator:
    """Placeholder for loading a calibrated system."""
    raise NotImplementedError("Implement your calibration loading logic")


def get_current_frame_from_cameras() -> dict[CameraIdString, CameraNodeOutputMessage]:
    """Placeholder for getting current frame from camera system."""
    raise NotImplementedError("Implement your camera frame acquisition logic")


def recording_active() -> bool:
    """Placeholder for checking if recording is active."""
    raise NotImplementedError("Implement your recording state logic")


if __name__ == "__main__":
    # Example: Load existing calibration and triangulate
    calibrator_pickle_path = Path("path/to/saved_calibrator.pkl")
    
    if calibrator_pickle_path.exists():
        import pickle
        
        calibrator: MultiCameraCalibrator = pickle.load(open(calibrator_pickle_path, "rb"))
        
        if not calibrator.has_calibration:
            logger.info("Running calibration...")
            calibrator.calibrate()
        
        # Create triangulator
        triangulator = create_triangulator_from_calibrator(calibrator)
        
        # Save to TOML for future use
        save_triangulator_to_toml(triangulator, "calibration.toml")
        
        # Later, load from TOML directly
        triangulator_loaded = PointTriangulator.from_toml("calibration.toml")
        
        logger.info("Ready for fast triangulation!")
