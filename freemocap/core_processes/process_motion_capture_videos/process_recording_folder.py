import logging
import multiprocessing
from typing import Optional


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
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.logging.configure_logging import log_view_logging_format_string
from freemocap.utilities.geometry.rotate_by_90_degrees_around_x_axis import rotate_by_90_degrees_around_x_axis
from freemocap.utilities.kill_event_exception import KillEventException

logger = logging.getLogger(__name__)


def process_recording_folder(
    recording_processing_parameter_model: ProcessingParameterModel,
    kill_event: multiprocessing.Event = None,
    logging_queue: Optional[multiprocessing.Queue] = None,
    use_tqdm: bool = True,
) -> None:
    """

    Parameters
    ----------
    recording_processing_parameter_model : ProcessingParameterModel
        ProcessingParameterModel object (contains all the paths and parameters necessary to process a session folder)

    kill_event : multiprocessing.Event
        Event to kill the process

    logging_queue : multiprocessing.Queue
        Queue to communicate logging between processes

    use_tqdm : bool
        Whether or not to use tqdm to show progress bar in terminal

    """
    if logging_queue:
        handler = DirectQueueHandler(logging_queue)
        handler.setFormatter(logging.Formatter(fmt=log_view_logging_format_string, datefmt="%Y-%m-%dT%H:%M:%S"))
        logger.addHandler(handler)

    try:
        processing_pipeline_check(processing_parameters=recording_processing_parameter_model)
    except FileNotFoundError as e:
        logger.error(
            "processing parameters are not valid for recording status"
            f" ::: {e}")
        if logging_queue:
            logging_queue.put(e)
        raise e

    try:
        image_data_numCams_numFrames_numTrackedPts_XYZ = run_image_tracking_pipeline(
            processing_parameters=recording_processing_parameter_model,
            kill_event=kill_event,
            queue=logging_queue,
            use_tqdm=use_tqdm,
        )
    except (RuntimeError, ValueError) as e:
        logger.error("2D skeleton detection failed, cannot continue processing")
        if logging_queue:
            logging_queue.put(e)
        raise e

    if kill_event is not None and kill_event.is_set():
        exception = KillEventException("Process was killed")
        if logging_queue:
            logging_queue.put(exception)
        raise exception

    try:
        raw_skel3d_frame_marker_xyz = get_triangulated_data(
            image_data_numCams_numFrames_numTrackedPts_XYZ=image_data_numCams_numFrames_numTrackedPts_XYZ,
            processing_parameters=recording_processing_parameter_model,
            kill_event=kill_event,
            queue=logging_queue,
        )
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        logger.error("Triangulation failed, cannot continue processing")
        if logging_queue:
            logging_queue.put(e)
        raise e

    if kill_event is not None and kill_event.is_set():
        exception = KillEventException("Process was killed")
        if logging_queue:
            logging_queue.put(exception)
        raise exception

    try:
        # TODO: move the rotate by 90 function into skellyforge to skip duplication of responsibility
        rotated_raw_skel3d_frame_marker_xyz = rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz)
        # TODO: find out if skellyforge does all the error handling we need - if not add it to post_process_data
        skel3d_frame_marker_xyz = post_process_data(
            recording_processing_parameter_model=recording_processing_parameter_model,
            raw_skel3d_frame_marker_xyz=rotated_raw_skel3d_frame_marker_xyz,
            queue=logging_queue,
        )
    except (RuntimeError, ValueError, AttributeError) as e:
        logger.error("Post processing failed, cannot continue processing")
        if logging_queue:
            logging_queue.put(e)
        raise e

    if kill_event is not None and kill_event.is_set():
        exception = KillEventException("Process was killed")
        if logging_queue:
            logging_queue.put(exception)
        raise exception

    try:
        anatomical_data_dict = calculate_anatomical_data(
            processing_parameters=recording_processing_parameter_model,
            skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
            queue=logging_queue,
        )
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as e:
        logger.error("Anatomical data calculation failed, cannot continue processing")
        if logging_queue:
            logging_queue.put(e)
        raise e

    if kill_event is not None and kill_event.is_set():
        exception = KillEventException("Process was killed")
        if logging_queue:
            logging_queue.put(exception)
        raise exception

    # TODO: deprecate save_data function in favor of DataSaver
    save_data(
        skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
        segment_COM_frame_imgPoint_XYZ=anatomical_data_dict["segment_COM"],
        totalBodyCOM_frame_XYZ=anatomical_data_dict["total_body_COM"],
        rigid_bones_data=anatomical_data_dict["rigid_bones_data"],
        processing_parameters=recording_processing_parameter_model,
        queue=logging_queue,
    )
    DataSaver(
        recording_folder_path=recording_processing_parameter_model.recording_info_model.path,
        model_info=recording_processing_parameter_model.tracking_model_info,
    ).save_all()

    logger.info(f"Done processing {recording_processing_parameter_model.recording_info_model.path}")
