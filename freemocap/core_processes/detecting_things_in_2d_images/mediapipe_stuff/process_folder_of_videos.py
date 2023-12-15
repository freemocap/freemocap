from typing import Optional
from pathlib import Path
import logging
import numpy as np
from multiprocessing import Pool

from skelly_tracker.trackers.base_tracker.base_tracker import BaseTracker
from skelly_tracker.trackers.mediapipe_tracker.mediapipe_holistic_tracker import MediapipeHolisticTracker
from skelly_tracker.trackers.yolo_mediapipe_combo_tracker.yolo_mediapipe_combo_tracker import YOLOMediapipeComboTracker

logger = logging.getLogger(__name__)

file_name_dictionary = {
    "MediapipeHolisticTracker": "mediapipe2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy",
    "YOLOMediapipeComboTracker": "mediapipe2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy",
}


def get_tracker(tracker_type: str, tracking_params) -> BaseTracker:
    match tracker_type:
        case "MediapipeHolisticTracker":
            tracker = MediapipeHolisticTracker(
                model_complexity=tracking_params.mediapipe_model_complexity,
                min_detection_confidence=tracking_params.min_detection_confidence,
                min_tracking_confidence=tracking_params.min_tracking_confidence,
                static_image_mode=tracking_params.static_image_mode,
            )

        case "YOLOMediapipeComboTracker":
            tracker = YOLOMediapipeComboTracker(
                model_complexity=tracking_params.mediapipe_model_complexity,
                min_detection_confidence=tracking_params.min_detection_confidence,
                min_tracking_confidence=tracking_params.min_tracking_confidence,
                static_image_mode=True,
            )

    return tracker


def process_single_video(tracker_type, tracking_params, video_path, annotated_video_path):
    video_name = video_path.stem + "_mediapipe.mp4"
    tracker = get_tracker(tracker_type, tracking_params)
    logger.info(f"Processing video: {video_name} with tracker: {tracker.__class__.__name__}")
    output_array = tracker.process_video(
        input_video_filepath=video_path,
        output_video_filepath=annotated_video_path / video_name,
        save_data_bool=False,
    )
    tracker.recorder.clear_recorded_objects()
    return output_array


def process_folder_of_videos(
    tracker_type: str,
    tracking_params,
    synchronized_video_path: Path,
    output_path: Optional[Path] = None,
    annotated_video_path: Optional[Path] = None,
    num_processes: int = None,
) -> None:
    """
    Process a folder of synchronized videos with the given tracker.
    Tracked data will be saved to a .npy file with the shape (numCams, numFrames, numTrackedPoints, pixelXYZ).

    :param synchronized_video_path: Path to folder of synchronized videos.
    :param tracker: Tracker to use.
    :param use_multiprocessing: Flag to enable multiprocessing.
    :return: Array of tracking data
    """
    synchronized_video_path = Path(synchronized_video_path)

    file_name = file_name_dictionary[tracker_type]

    if num_processes is None:
        num_processes = 1  # TODO: figure out number of processor cores and set to that minus 1

    # file_name = file_name_dictionary[tracker.__class__.__name__]
    if output_path is None:
        output_path = synchronized_video_path.parent / "output_data" / "raw_data" / file_name
    if not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    if annotated_video_path is None:
        annotated_video_path = synchronized_video_path.parent / "annotated_videos"
    if not annotated_video_path.exists():
        annotated_video_path.mkdir(parents=True, exist_ok=True)

    tasks = [
        (tracker_type, tracking_params, video_path, annotated_video_path)
        for video_path in synchronized_video_path.glob("*.mp4")
    ]

    if num_processes > 1:
        logging.info("Using multiprocessing to run pose estimation")
        with Pool(processes=num_processes) as pool:
            array_list = pool.starmap(process_single_video, tasks)
    else:
        array_list = []
        for task in tasks:
            array_list.append(process_single_video(*task))

    combined_array = np.stack(array_list)

    logger.info(f"Shape of output array: {combined_array.shape}")
    # np.save(output_path, combined_array)

    return combined_array
