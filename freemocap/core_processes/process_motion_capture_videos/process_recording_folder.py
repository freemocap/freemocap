import logging
import numpy as np
import multiprocessing
from pathlib import Path

import pandas as pd

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.mediapipe_skeleton_names_and_connections import (
    mediapipe_names_and_connections_dict,
)
from freemocap.core_processes.post_process_skeleton_data.post_process_skeleton import post_process_data
from freemocap.core_processes.post_process_skeleton_data.process_single_camera_skeleton_data import \
    process_single_camera_skeleton_data
from freemocap.system.paths_and_files_names import (
    MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME,
    RAW_DATA_FOLDER_NAME,
    RECORDING_PARAMETER_DICT_JSON_FILE_NAME,
)
from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.get_anipose_calibration_object import (
    load_anipose_calibration_toml_from_path,
)
from freemocap.core_processes.capture_volume_calibration.triangulate_3d_data import (
    triangulate_3d_data,
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

from freemocap.tests.test_image_tracking_data_shape import (
    test_image_tracking_data_shape,
)
from freemocap.tests.test_mediapipe_skeleton_data_shape import test_mediapipe_skeleton_data_shape
from freemocap.utilities.rotate_by_90_degrees_around_x_axis import rotate_by_90_degrees_around_x_axis
from freemocap.utilities.save_dictionary_to_json import save_dictionary_to_json

logger = logging.getLogger(__name__)


def process_recording_folder(
        recording_processing_parameter_model: RecordingProcessingParameterModel,
        kill_event: multiprocessing.Event = None,
):
    """

    Parameters
    ----------
    recording_processing_parameter_model : RecordingProcessingParameterModel
        RecordingProcessingParameterModel object (contains all the paths and parameters necessary to process a session folder

    """

    rec = recording_processing_parameter_model  # make it smol

    if not Path(rec.recording_info_model.synchronized_videos_folder_path).exists():
        raise FileNotFoundError(
            f"Could not find synchronized_videos folder at {rec.recording_info_model.synchronized_videos_folder_path}"
        )

    
    logger.info("Detecting 2d skeletons...")
    if rec.mediapipe_parameters_model.skip_2d_image_tracking:
        try: 
            mediapipe_image_data_numCams_numFrames_numTrackedPts_XYZ = np.load(rec.recording_info_model.mediapipe_2d_data_npy_file_path)
        except Exception as e:
            logger.error("Failed to load 2D data, cannot continue processing")
            return
    else:
        # 2d skeleton detection
        mediapipe_skeleton_detector = MediaPipeSkeletonDetector(
            parameter_model=rec.mediapipe_parameters_model,
        )

        mediapipe_image_data_numCams_numFrames_numTrackedPts_XYZ = mediapipe_skeleton_detector.process_folder_full_of_videos(
            rec.recording_info_model.synchronized_videos_folder_path,
            Path(rec.recording_info_model.output_data_folder_path) / RAW_DATA_FOLDER_NAME,
            kill_event=kill_event,
        )

    if kill_event is not None and kill_event.is_set():
        return

    try:
        assert test_image_tracking_data_shape(
            synchronized_video_folder_path=rec.recording_info_model.synchronized_videos_folder_path,
            image_tracking_data_file_name=rec.recording_info_model.mediapipe_2d_data_npy_file_path,
        )
    except AssertionError as error_message:
            logger.error(error_message)

    # spoof 3D data if single camera
    if mediapipe_image_data_numCams_numFrames_numTrackedPts_XYZ.shape[0] == 1:

        (raw_skel3d_frame_marker_xyz, skeleton_reprojection_error_fr_mar) = process_single_camera_skeleton_data(
            input_image_data_frame_marker_xyz=mediapipe_image_data_numCams_numFrames_numTrackedPts_XYZ[0],
            raw_data_folder_path=Path(rec.recording_info_model.raw_data_folder_path))

    else:
        if rec.anipose_triangulate_3d_parameters_model.skip_3d_triangulation:
            raw_skel3d_frame_marker_xyz = np.load(rec.recording_info_model.raw_mediapipe_3d_data_npy_file_path)
            skeleton_reprojection_error_fr_mar = np.load(rec.recording_info_model.mediapipe_reprojection_error_data_npy_file_path)
        else:
            logger.info("Triangulating 3d skeletons...")

            assert rec.recording_info_model.calibration_toml_check, f"No calibration file found at: {rec.recording_info_model.calibration_toml_path}"
            assert rec.recording_info_model.data2d_status_check, f"No mediapipe 2d data found at: {rec.recording_info_model.mediapipe_2d_data_npy_file_path}"

            anipose_calibration_object = load_anipose_calibration_toml_from_path(
                camera_calibration_data_toml_path=rec.recording_info_model.calibration_toml_path,
                save_copy_of_calibration_to_this_path=rec.recording_info_model.path,
            )
            (raw_skel3d_frame_marker_xyz, skeleton_reprojection_error_fr_mar,) = triangulate_3d_data(
                anipose_calibration_object=anipose_calibration_object,
                mediapipe_2d_data=mediapipe_image_data_numCams_numFrames_numTrackedPts_XYZ[:, :, :, :2],
                output_data_folder_path=rec.recording_info_model.raw_data_folder_path,
                mediapipe_confidence_cutoff_threshold=rec.anipose_triangulate_3d_parameters_model.confidence_threshold_cutoff,
                use_triangulate_ransac=rec.anipose_triangulate_3d_parameters_model.use_triangulate_ransac_method,
                kill_event=kill_event,
            )

    if kill_event is not None and kill_event.is_set():
        return

    try:
        assert test_mediapipe_skeleton_data_shape(
            synchronized_video_folder_path=rec.recording_info_model.synchronized_videos_folder_path,
            raw_skeleton_npy_file_path=rec.recording_info_model.raw_mediapipe_3d_data_npy_file_path,
            reprojection_error_file_name=rec.recording_info_model.mediapipe_reprojection_error_data_npy_file_path,
        )
    except AssertionError as error_message:
        logger.error(error_message)

    post_process_data(recording_processing_parameter_model = recording_processing_parameter_model,
                      raw_skel3d_frame_marker_xyz= raw_skel3d_frame_marker_xyz,
                      path_to_folder_where_we_will_save_this_data=rec.recording_info_model.output_data_folder_path)

    # #rotate so skeleton is closer to 'vertical' in a z-up reference frame
    # rotated_raw_skel3d_frame_marker_xyz = rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz)
    #
    #
    # logger.info("Gap-filling, butterworth filtering, origin aligning 3d skeletons, then calculating center of mass ...")
    #
    # skel3d_frame_marker_xyz = gap_fill_filter_origin_align_3d_data_and_then_calculate_center_of_mass(
    #     raw_skel3d_frame_marker_xyz=rotated_raw_skel3d_frame_marker_xyz,
    #     skeleton_reprojection_error_fr_mar=skeleton_reprojection_error_fr_mar,
    #     path_to_folder_where_we_will_save_this_data=rec.recording_info_model.output_data_folder_path,
    #     skip_butterworth_filter=rec.post_processing_parameters_model.skip_butterworth_filter,
    #     sampling_rate=rec.post_processing_parameters_model.framerate,
    #     cut_off=rec.post_processing_parameters_model.butterworth_filter_parameters.cutoff_frequency,
    #     order=rec.post_processing_parameters_model.butterworth_filter_parameters.order,
    #     reference_frame_number=None,
    # )

    try:
        test_mediapipe_skeleton_data_shape(
            synchronized_video_folder_path=rec.recording_info_model.synchronized_videos_folder_path,
            raw_skeleton_npy_file_path=rec.recording_info_model.mediapipe_3d_data_npy_file_path,
            reprojection_error_file_name=rec.recording_info_model.mediapipe_reprojection_error_data_npy_file_path,
        )
    except AssertionError as error_message:
        logger.error(error_message)


    logger.info("Breaking up big `npy` into smaller bits and converting to `csv`...")
    # break up big NPY and save out csv's
    convert_mediapipe_npy_to_csv(
        mediapipe_3d_frame_trackedPoint_xyz=skel3d_frame_marker_xyz,
        output_data_folder_path=rec.recording_info_model.output_data_folder_path,
    )

    path_to_skeleton_body_csv = (
            Path(rec.recording_info_model.output_data_folder_path) / MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME
    )
    skeleton_dataframe = pd.read_csv(path_to_skeleton_body_csv)

    logger.info("Estimating skeleton segment lengths...")
    skeleton_segment_lengths_dict = estimate_skeleton_segment_lengths(
        skeleton_dataframe=skeleton_dataframe,
        skeleton_segment_definitions=mediapipe_skeleton_segment_definitions,
    )

    save_dictionary_to_json(
        save_path=rec.recording_info_model.output_data_folder_path,
        file_name="mediapipe_skeleton_segment_lengths.json",
        dictionary=skeleton_segment_lengths_dict,
    )

    save_dictionary_to_json(
        save_path=rec.recording_info_model.output_data_folder_path,
        file_name="mediapipe_names_and_connections_dict.json",
        dictionary=mediapipe_names_and_connections_dict,
    )
