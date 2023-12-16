import logging
import multiprocessing
from pathlib import Path
import numpy as np

from skelly_tracker.process_folder_of_videos import process_folder_of_videos

from freemocap.data_layer.recording_models.post_processing_parameter_models import (
    ProcessingParameterModel,
)
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.logging.configure_logging import log_view_logging_format_string
from freemocap.system.paths_and_filenames.file_and_folder_names import RAW_DATA_FOLDER_NAME

logger = logging.getLogger(__name__)


def get_image_data(
    processing_parameters: ProcessingParameterModel,
    kill_event: multiprocessing.Event,
    queue: multiprocessing.Queue,
    use_tqdm: bool,
) -> np.ndarray:
    if queue:
        handler = DirectQueueHandler(queue)
        handler.setFormatter(logging.Formatter(fmt=log_view_logging_format_string, datefmt="%Y-%m-%dT%H:%M:%S"))
        logger.addHandler(handler)

    if not processing_parameters.mediapipe_parameters_model.run_image_tracking:
        logger.info(
            f"Skipping 2d skeleton detection and loading data from: {processing_parameters.recording_info_model.mediapipe_2d_data_npy_file_path}"
        )
        try:
            image_data_numCams_numFrames_numTrackedPts_XYZ = np.load(
                processing_parameters.recording_info_model.mediapipe_2d_data_npy_file_path
            )
        except Exception as e:
            logger.error(e)
            raise RuntimeError("Failed to load 2D data, cannot continue processing") from e
    else:
        logger.info("Detecting 2d skeletons...")
        # 2d skeleton detection
        image_data_numCams_numFrames_numTrackedPts_XYZ = run_image_tracking(
            tracking_params=processing_parameters.mediapipe_parameters_model,
            synchronized_videos_folder_path=Path(
                processing_parameters.recording_info_model.synchronized_videos_folder_path
            ),
            output_data_folder_path=Path(processing_parameters.recording_info_model.output_data_folder_path)
            / RAW_DATA_FOLDER_NAME,
            kill_event=kill_event,
            use_tqdm=use_tqdm,
        )

    if not processing_parameters.recording_info_model.data2d_status_check:
        raise FileNotFoundError(
            f"No mediapipe 2d data found at: {processing_parameters.recording_info_model.mediapipe_2d_data_npy_file_path}"
        )

    return image_data_numCams_numFrames_numTrackedPts_XYZ


def run_image_tracking(
    tracking_params: ProcessingParameterModel,
    synchronized_videos_folder_path: Path,
    output_data_folder_path: Path,
    kill_event: multiprocessing.Event = None,
    use_tqdm: bool = True,
):
    # tracker_type = 'MediapipeHolisticTracker'
    tracker_type = "YOLOMediapipeComboTracker"  # TODO: read this from tracking params

    image_data_numCams_numFrames_numTrackedPts_XYZ = process_folder_of_videos(
        tracker_name=tracker_type,
        tracking_params=tracking_params,
        synchronized_video_path=synchronized_videos_folder_path,
        output_folder_path=output_data_folder_path,
        annotated_video_path=None,
        num_processes=None,  # TODO: change the use multiprocessing bool to num_processes
    )

    return image_data_numCams_numFrames_numTrackedPts_XYZ
