import logging
import multiprocessing
from pathlib import Path

import numpy as np
from skellytracker.process_folder_of_videos import process_folder_of_videos
from skellytracker.trackers.base_tracker.base_tracking_params import (
    BaseTrackingParams,
)
from skellytracker.trackers.base_tracker.model_info import ModelInfo

from freemocap.data_layer.recording_models.post_processing_parameter_models import (
    ProcessingParameterModel,
)
from freemocap.system.logging.configure_logging import log_view_logging_format_string
from freemocap.system.logging.queue_logger import DirectQueueHandler
from freemocap.system.paths_and_filenames.file_and_folder_names import LOG_VIEW_PROGRESS_BAR_STRING, RAW_DATA_FOLDER_NAME
from freemocap.tests.test_image_tracking_data_shape import test_image_tracking_data_shape

logger = logging.getLogger(__name__)


def run_image_tracking_pipeline(
    processing_parameters: ProcessingParameterModel,
    kill_event: multiprocessing.Event,
    queue: multiprocessing.Queue,
    use_tqdm: bool,
) -> np.ndarray:
    if queue:
        handler = DirectQueueHandler(queue)
        handler.setFormatter(logging.Formatter(fmt=log_view_logging_format_string, datefmt="%Y-%m-%dT%H:%M:%S"))
        logger.addHandler(handler)

    if not processing_parameters.tracking_parameters_model.run_image_tracking:
        logger.info(
            f"Skipping 2d skeleton detection and loading data from: {processing_parameters.recording_info_model.data_2d_npy_file_path}"
        )
        try:
            image_data_numCams_numFrames_numTrackedPts_XYZ = np.load(
                processing_parameters.recording_info_model.data_2d_npy_file_path
            )
        except Exception as e:
            logger.error(e)
            raise RuntimeError("Failed to load 2D data, cannot continue processing") from e
    else:
        logger.info("Detecting 2d skeletons...")
        logger.info(LOG_VIEW_PROGRESS_BAR_STRING)
        # 2d skeleton detection
        image_data_numCams_numFrames_numTrackedPts_XYZ = run_image_tracking(
            model_info=processing_parameters.tracking_model_info,
            tracking_params=processing_parameters.tracking_parameters_model,
            synchronized_videos_folder_path=Path(
                processing_parameters.recording_info_model.synchronized_videos_folder_path
            ),
            output_data_folder_path=Path(processing_parameters.recording_info_model.output_data_folder_path)
            / RAW_DATA_FOLDER_NAME,
            kill_event=kill_event,
            use_tqdm=use_tqdm,
        )

    # TODO: check that skellytracker saved out data correctly
    try:
        test_image_tracking_data_shape(
            synchronized_video_folder_path=processing_parameters.recording_info_model.synchronized_videos_folder_path,
            image_tracking_data=image_data_numCams_numFrames_numTrackedPts_XYZ,
        )
    except (ValueError, AssertionError) as e:
        logger.error(e)
        raise ValueError("image tracking data is not valid, cannot continue processing")

    return image_data_numCams_numFrames_numTrackedPts_XYZ


def run_image_tracking(
    model_info: ModelInfo,
    tracking_params: BaseTrackingParams,
    synchronized_videos_folder_path: Path,
    output_data_folder_path: Path,
    kill_event: multiprocessing.Event = None,
    use_tqdm: bool = True,
):
    if hasattr(tracking_params, "use_yolo_crop_method") and tracking_params.use_yolo_crop_method:
        model_info.tracker_name = "YOLOMediapipeComboTracker"
    # TODO: this shouldn't be handled here

    image_data_numCams_numFrames_numTrackedPts_XYZ = process_folder_of_videos(
        model_info=model_info,
        tracking_params=tracking_params,
        synchronized_video_path=synchronized_videos_folder_path,
        output_folder_path=output_data_folder_path,
        annotated_video_path=None,
        num_processes=tracking_params.num_processes,
    )

    return image_data_numCams_numFrames_numTrackedPts_XYZ
