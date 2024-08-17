import logging

from freemocap.core_processes.post_process_skeleton_data.post_process_skeleton import post_process_data
from freemocap.core_processes.process_motion_capture_videos.processing_pipeline_functions.anatomical_data_pipeline_functions import (
    calculate_anatomical_data,
)
from freemocap.core_processes.process_motion_capture_videos.processing_pipeline_functions.data_saving_pipeline_functions import (
    save_data,
)
from freemocap.core_processes.process_motion_capture_videos.processing_pipeline_functions.image_tracking_pipeline_functions import (
    run_image_tracking_pipeline,
)
from freemocap.core_processes.process_motion_capture_videos.processing_pipeline_functions.pipeline_check import (
    processing_pipeline_check,
)
from freemocap.core_processes.process_motion_capture_videos.processing_pipeline_functions.triangulation_pipeline_functions import (
    get_triangulated_data,
)
from freemocap.data_layer.data_saver.data_saver import DataSaver
from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.utilities.geometry.rotate_by_90_degrees_around_x_axis import rotate_by_90_degrees_around_x_axis

logger = logging.getLogger(__name__)


def process_recording_folder(recording_processing_parameter_model: ProcessingParameterModel):

    try:
        processing_pipeline_check(processing_parameters=recording_processing_parameter_model)
    except FileNotFoundError as e:
        logger.error("processing parameters are not valid for recording status")
        raise e

    try:
        image_data_numCams_numFrames_numTrackedPts_XYZ = run_image_tracking_pipeline(
            processing_parameters=recording_processing_parameter_model)
    except (RuntimeError, FileNotFoundError) as e:
        logger.error("2D skeleton detection failed, cannot continue processing")
        raise e

    try:
        raw_skel3d_frame_marker_xyz = get_triangulated_data(
            image_data_numCams_numFrames_numTrackedPts_XYZ=image_data_numCams_numFrames_numTrackedPts_XYZ,
            processing_parameters=recording_processing_parameter_model,
        )
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        logger.error("Triangulation failed, cannot continue processing")
        raise e

    rotated_raw_skel3d_frame_marker_xyz = rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz)
    skel3d_frame_marker_xyz = post_process_data(
        recording_processing_parameter_model=recording_processing_parameter_model,
        raw_skel3d_frame_marker_xyz=rotated_raw_skel3d_frame_marker_xyz,
    )

    anatomical_data_dict = calculate_anatomical_data(
        processing_parameters=recording_processing_parameter_model,
        skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
    )

    save_data(
        skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
        segment_COM_frame_imgPoint_XYZ=anatomical_data_dict["segment_COM"],
        totalBodyCOM_frame_XYZ=anatomical_data_dict["total_body_COM"],
        processing_parameters=recording_processing_parameter_model,
    )
    DataSaver(recording_folder_path=recording_processing_parameter_model.recording_info_model.path).save_all()

    logger.info(f"Done processing {recording_processing_parameter_model.recording_info_model.path}")
