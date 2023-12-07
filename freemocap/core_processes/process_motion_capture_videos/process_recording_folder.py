import logging
import multiprocessing
from pathlib import Path
import numpy as np
from freemocap.core_processes.post_process_skeleton_data.calculate_center_of_mass import run_center_of_mass_calculations
from freemocap.core_processes.post_process_skeleton_data.post_process_skeleton import post_process_data
from freemocap.core_processes.process_motion_capture_videos.processing_pipeline_functions.anatomical_data_pipeline_functions import (
    calculate_anatomical_data,
)
from freemocap.core_processes.process_motion_capture_videos.processing_pipeline_functions.data_saving_pipeline_functions import (
    save_data,
)

from freemocap.core_processes.process_motion_capture_videos.processing_pipeline_functions.image_tracking_pipeline_functions import (
    get_image_data,
)
from freemocap.core_processes.process_motion_capture_videos.processing_pipeline_functions.triangulation_pipeline_functions import (
    get_triangulated_data,
)
from freemocap.data_layer.data_saver.data_saver import DataSaver
from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.logging.configure_logging import log_view_logging_format_string
from freemocap.system.paths_and_filenames.file_and_folder_names import RAW_DATA_FOLDER_NAME
from freemocap.utilities.geometry.rotate_by_90_degrees_around_x_axis import rotate_by_90_degrees_around_x_axis

logger = logging.getLogger(__name__)


def process_recording_folder(
    recording_processing_parameter_model: ProcessingParameterModel,
    kill_event: multiprocessing.Event = None,
    queue: multiprocessing.Queue = None,
    use_tqdm: bool = True,
) -> None:
    """

    Parameters
    ----------
    recording_processing_parameter_model : ProcessingParameterModel
        ProcessingParameterModel object (contains all the paths and parameters necessary to process a session folder)

    kill_event : multiprocessing.Event
        Event to kill the process

    queue : multiprocessing.Queue
        Queue to communicate logging between processes

    use_tqdm : bool
        Whether or not to use tqdm to show progress bar in terminal


    """
    if queue:
        handler = DirectQueueHandler(queue)
        handler.setFormatter(logging.Formatter(fmt=log_view_logging_format_string, datefmt="%Y-%m-%dT%H:%M:%S"))
        logger.addHandler(handler)

    check_synchronized_videos_folder_exists(
        processing_parameters=recording_processing_parameter_model
    )  # TODO: This can maybe just be another status check?

    image_data_numCams_numFrames_numTrackedPts_XYZ = get_image_data(
        processing_parameters=recording_processing_parameter_model,
        kill_event=kill_event,
        queue=queue,
        use_tqdm=use_tqdm,
    )

    if kill_event is not None and kill_event.is_set():
        logger.info("Process was killed")
        return

    raw_skel3d_frame_marker_xyz = get_triangulated_data(
        image_data_numCams_numFrames_numTrackedPts_XYZ=image_data_numCams_numFrames_numTrackedPts_XYZ,
        processing_parameters=recording_processing_parameter_model,
        kill_event=kill_event,
        queue=queue,
    )

    if kill_event is not None and kill_event.is_set():
        logger.info("Process was killed")
        return

    # TODO: move the rotate by 90 function into skellyforge to skip duplication of responsibility
    rotated_raw_skel3d_frame_marker_xyz = rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz)
    # TODO: find out if skellyforge does all the error handling we need - if not add it to post_process_data
    skel3d_frame_marker_xyz = post_process_data(
        recording_processing_parameter_model=recording_processing_parameter_model,
        raw_skel3d_frame_marker_xyz=rotated_raw_skel3d_frame_marker_xyz,
        queue=queue,
    )

    if kill_event is not None and kill_event.is_set():
        logger.info("Process was killed")
        return

    anatomical_data_dict = calculate_anatomical_data(
        processing_parameters=recording_processing_parameter_model,
        skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
        queue=queue,
    )

    if kill_event is not None and kill_event.is_set():
        logger.info("Process was killed")
        return

    # TODO: deprecate save_data function in favor of DataSaver
    DataSaver(recording_folder_path=recording_processing_parameter_model.recording_info_model.path).save_all()
    save_data(
        skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
        segment_COM_frame_imgPoint_XYZ=anatomical_data_dict["segment_COM"],
        totalBodyCOM_frame_XYZ=anatomical_data_dict["total_body_COM"],
        skeleton_segment_lengths_dict=anatomical_data_dict["skeleton_segment_lengths"],
        processing_parameters=recording_processing_parameter_model,
        queue=queue,
    )

    logger.info(f"Done processing {recording_processing_parameter_model.recording_info_model.path}")


def check_synchronized_videos_folder_exists(processing_parameters: ProcessingParameterModel):
    if not Path(processing_parameters.recording_info_model.synchronized_videos_folder_path).exists():
        raise FileNotFoundError(
            f"Could not find synchronized_videos folder at {processing_parameters.recording_info_model.synchronized_videos_folder_path}"
        )
