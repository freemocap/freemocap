import logging
from pathlib import Path

import numpy as np
import pandas as pd

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.mediapipe_skeleton_names_and_connections import (
    mediapipe_names_and_connections_dict,
)
from freemocap.core_processes.post_process_skeleton_data.process_single_camera_3d_data import \
    process_single_camera_skeleton_data
from freemocap.system.paths_and_files_names import (
    MEDIAPIPE_BODY_DATAFRAME_CSV_FILE_NAME,
    RAW_DATA_FOLDER_NAME,
)
from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.get_anipose_calibration_object import (
    load_anipose_calibration_toml_from_path,
)
from freemocap.core_processes.capture_volume_calibration.triangulate_3d_data import (
    triangulate_3d_data, save_mediapipe_skeleton_data_to_npy,
)
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.convert_mediapipe_npy_to_csv import (
    convert_mediapipe_npy_to_csv,
)
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.mediapipe_skeleton_detector import (
    MediaPipeSkeletonDetector,
)
from freemocap.core_processes.post_process_skeleton_data.estimate_skeleton_segment_lengths import (
    estimate_skeleton_segment_lengths,
    mediapipe_skeleton_segment_definitions,
)
from freemocap.core_processes.post_process_skeleton_data.gap_fill_filter_and_origin_align_skeleton_data import (
    gap_fill_filter_origin_align_3d_data_and_then_calculate_center_of_mass,
)
from freemocap.parameter_info_models.recording_processing_parameter_models import RecordingProcessingParameterModel

from freemocap.tests.test_mediapipe_2d_data_shape import (
    test_mediapipe_image_data_shape,
)
from freemocap.tests.test_mediapipe_3d_data_shape import test_mediapipe_3d_data_shape
from freemocap.utilities.save_dictionary_to_json import save_dictionary_to_json
from freemocap.utilities.rotate_by_90_degrees_around_x_axis import rotate_by_90_degrees_around_x_axis

logger = logging.getLogger(__name__)


def process_session_folder(
    session_processing_parameter_model: RecordingProcessingParameterModel,
):
    """
    Process a single session folder.

    Parameters
    ----------
    session_processing_parameter_model : RecordingProcessingParameterModel
        SessionProcessingParameterModel object (contains all the paths and parameters necessary to process a session folder

    """

    s = session_processing_parameter_model  # make it smol

    if not Path(s.recording_info_model.synchronized_videos_folder_path).exists():
        raise FileNotFoundError(
            f"Could not find synchronized_videos folder at {s.recording_info_model.synchronized_videos_folder_path}"
        )

    logger.info("Detecting 2d skeletons...")
    # 2d skeleton detection
    mediapipe_skeleton_detector = MediaPipeSkeletonDetector(
        parameter_model=s.mediapipe_parameters_model,
    )

    mediapipe_image_data_numCams_numFrames_numTrackedPts_XYZ = mediapipe_skeleton_detector.process_folder_full_of_videos(
        s.recording_info_model.synchronized_videos_folder_path,
        Path(s.recording_info_model.output_data_folder_path) / RAW_DATA_FOLDER_NAME,
    )

    assert test_mediapipe_image_data_shape(
        synchronized_videos_folder=s.recording_info_model.synchronized_videos_folder_path,
        mediapipe_image_data_file_path=s.recording_info_model.mediapipe_image_data_npy_file_path,
    )

    # spoof 3D data if single camera
    if mediapipe_image_data_numCams_numFrames_numTrackedPts_XYZ.shape[0] == 1:

        (raw_skel3d_frame_marker_xyz, skeleton_reprojection_error_fr_mar) = process_single_camera_skeleton_data(
            input_image_data_frame_marker_xyz=mediapipe_image_data_numCams_numFrames_numTrackedPts_XYZ[0],
            raw_data_folder_path=Path(s.recording_info_model.raw_data_folder_path))

    else:

        logger.info("Triangulating 3d skeletons...")

        anipose_calibration_object = load_anipose_calibration_toml_from_path(
            camera_calibration_data_toml_path=s.recording_info_model.calibration_toml_file_path,
            save_copy_of_calibration_to_this_path=s.recording_info_model.path,
        )
        (raw_skel3d_frame_marker_xyz, skeleton_reprojection_error_fr_mar,) = triangulate_3d_data(
            anipose_calibration_object=anipose_calibration_object,
            mediapipe_2d_data=mediapipe_image_data_numCams_numFrames_numTrackedPts_XYZ[:, :, :, :2],
            output_data_folder_path=s.recording_info_model.raw_data_folder_path,
            mediapipe_confidence_cutoff_threshold=s.anipose_triangulate_3d_parameters_model.confidence_threshold_cutoff,
            use_triangulate_ransac=s.anipose_triangulate_3d_parameters_model.use_triangulate_ransac_method,
        )

    assert test_mediapipe_3d_data_shape(
        synchronized_videos_folder=s.recording_info_model.synchronized_videos_folder_path,
        mediapipe_3d_data_npy_path=s.recording_info_model.mediapipe_raw_skeleton_npy_file_path,
        medipipe_reprojection_error_data_npy_path=s.recording_info_model.mediapipe_reprojection_error_data_npy_file_path,
    )

    rotated_raw_skel3d_frame_marker_xyz = rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz)

    logger.info("Gap-filling, butterworth filtering, origin aligning 3d skeletons, then calculating center of mass ...")

    skel3d_frame_marker_xyz = gap_fill_filter_origin_align_3d_data_and_then_calculate_center_of_mass(
        skel3d_frame_marker_xyz=rotated_raw_skel3d_frame_marker_xyz,
        skeleton_reprojection_error_fr_mar=skeleton_reprojection_error_fr_mar,
        path_to_folder_where_we_will_save_this_data=s.recording_info_model.output_data_folder_path,
        sampling_rate=s.post_processing_parameters_model.framerate,
        cut_off=s.post_processing_parameters_model.butterworth_filter_parameters.cutoff_frequency,
        order=s.post_processing_parameters_model.butterworth_filter_parameters.order,
        reference_frame_number=None,
    )
    assert test_mediapipe_3d_data_shape(
        synchronized_videos_folder=s.recording_info_model.synchronized_videos_folder_path,
        mediapipe_3d_data_npy_path=s.recording_info_model.mediapipe_processed_data_npy_file_path,
        medipipe_reprojection_error_data_npy_path=s.recording_info_model.mediapipe_reprojection_error_data_npy_file_path,
    )

    logger.info("Breaking up big `npy` into smaller bits and converting to `csv`...")
    # break up big NPY and save out csv's
    convert_mediapipe_npy_to_csv(
        mediapipe_3d_frame_trackedPoint_xyz=skel3d_frame_marker_xyz,
        output_data_folder_path=s.recording_info_model.output_data_folder_path,
    )

    path_to_skeleton_body_csv = (
            Path(s.recording_info_model.output_data_folder_path) / MEDIAPIPE_BODY_DATAFRAME_CSV_FILE_NAME
    )
    skeleton_dataframe = pd.read_csv(path_to_skeleton_body_csv)

    logger.info("Estimating skeleton segment lengths...")
    skeleton_segment_lengths_dict = estimate_skeleton_segment_lengths(
        skeleton_dataframe=skeleton_dataframe,
        skeleton_segment_definitions=mediapipe_skeleton_segment_definitions,
    )

    save_dictionary_to_json(
        save_path=s.recording_info_model.output_data_folder_path,
        file_name="mediapipe_skeleton_segment_lengths.json",
        dictionary=skeleton_segment_lengths_dict,
    )
    save_dictionary_to_json(
        save_path=s.recording_info_model.output_data_folder_path,
        file_name="mediapipe_names_and_connections_dict.json",
        dictionary=mediapipe_names_and_connections_dict,
    )


if __name__ == "__main__":
    pass

