import logging
import multiprocessing
from pathlib import Path
import numpy as np

from freemocap.core_processes.capture_volume_calibration.triangulate_3d_data import triangulate_3d_data
from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.get_anipose_calibration_object import (
    load_anipose_calibration_toml_from_path,
)
from freemocap.core_processes.post_process_skeleton_data.process_single_camera_skeleton_data import (
    process_single_camera_skeleton_data,
)
from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.logging.configure_logging import log_view_logging_format_string

logger = logging.getLogger(__name__)


def get_triangulated_data(
    image_data_numCams_numFrames_numTrackedPts_XYZ: np.ndarray,
    processing_parameters: ProcessingParameterModel,
    kill_event: multiprocessing.Event = None,
    queue: multiprocessing.Queue = None,
) -> np.ndarray:
    if queue:
        handler = DirectQueueHandler(queue)
        handler.setFormatter(logging.Formatter(fmt=log_view_logging_format_string, datefmt="%Y-%m-%dT%H:%M:%S"))
        logger.addHandler(handler)

    if image_data_numCams_numFrames_numTrackedPts_XYZ.shape[0] == 1:
        logger.info("Skipping 3d triangulation for single camera data")
        (raw_skel3d_frame_marker_xyz, skeleton_reprojection_error_fr_mar) = process_single_camera_skeleton_data(
            input_image_data_frame_marker_xyz=image_data_numCams_numFrames_numTrackedPts_XYZ[0],
            raw_data_folder_path=Path(processing_parameters.recording_info_model.raw_data_folder_path),
        )
    elif not processing_parameters.anipose_triangulate_3d_parameters_model.run_3d_triangulation:
        logger.info(
            f"Skipping 3d triangulation and loading data from: {processing_parameters.recording_info_model.raw_mediapipe_3d_data_npy_file_path}"
        )
        try:
            raw_skel3d_frame_marker_xyz = np.load(
                processing_parameters.recording_info_model.raw_mediapipe_3d_data_npy_file_path
            )
            skeleton_reprojection_error_fr_mar = np.load(
                processing_parameters.recording_info_model.mediapipe_reprojection_error_data_npy_file_path
            )
        except Exception as e:
            logger.error(e)
            raise RuntimeError("Failed to load 3D data, cannot continue processing") from e
    else:
        logger.info("Triangulating 3d skeletons...")

        if not processing_parameters.recording_info_model.calibration_toml_check:
            raise FileNotFoundError(
                f"No calibration file found at: {processing_parameters.recording_info_model.calibration_toml_path}"
            )

        if not processing_parameters.recording_info_model.data2d_status_check:
            raise FileNotFoundError(
                f"No mediapipe 2d data found at: {processing_parameters.recording_info_model.mediapipe_2d_data_npy_file_path}"
            )

        anipose_calibration_object = load_anipose_calibration_toml_from_path(
            camera_calibration_data_toml_path=processing_parameters.recording_info_model.calibration_toml_path,
            save_copy_of_calibration_to_this_path=processing_parameters.recording_info_model.path,
        )
        (
            raw_skel3d_frame_marker_xyz,
            skeleton_reprojection_error_fr_mar,
        ) = triangulate_3d_data(
            anipose_calibration_object=anipose_calibration_object,
            mediapipe_2d_data=image_data_numCams_numFrames_numTrackedPts_XYZ[:, :, :, :2],
            output_data_folder_path=processing_parameters.recording_info_model.raw_data_folder_path,
            use_triangulate_ransac=processing_parameters.anipose_triangulate_3d_parameters_model.use_triangulate_ransac_method,
            kill_event=kill_event,
        )

    return raw_skel3d_frame_marker_xyz
