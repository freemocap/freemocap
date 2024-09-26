import multiprocessing
from pathlib import Path

from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel, AniposeTriangulate3DParametersModel, PostProcessingParametersModel
from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel
from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import process_recording_folder
from skellytracker.trackers.yolo_tracker.yolo_model_info import YOLOTrackingParams, YOLOModelInfo

def process_videos_YOLO(recording_folder: Path, num_processes: int = multiprocessing.cpu_count() - 1):
    """
    Process a recording folder from the synchronized videos
    """
    recording_model = RecordingInfoModel(
        recording_folder_path=recording_folder,
        active_tracker="yolo"
    )

    yolo_processing_parameters = ProcessingParameterModel(
        recording_info_model=recording_model,
        tracking_parameters_model=YOLOTrackingParams(
            num_processes=num_processes,
            model_size="medium",
        ),
        anipose_triangulate_3d_parameters_model=AniposeTriangulate3DParametersModel(),
        post_processing_parameters_model=PostProcessingParametersModel(),
        tracking_model_info=YOLOModelInfo(),
    )

    process_recording_folder(
        recording_processing_parameter_model=yolo_processing_parameters,
        kill_event=None,
        logging_queue=None,
    )

def process_raw_data_YOLO(recording_folder: Path):
    """
    Process a recording folder where raw, 2d data is already available
    """
    recording_model = RecordingInfoModel(
        recording_folder_path=recording_folder,
        active_tracker="yolo"
    )

    yolo_processing_parameters = ProcessingParameterModel(
        recording_info_model=recording_model,
        tracking_parameters_model=YOLOTrackingParams(
            run_image_tracking=False,
        ),
        anipose_triangulate_3d_parameters_model=AniposeTriangulate3DParametersModel(),
        post_processing_parameters_model=PostProcessingParametersModel(),
        tracking_model_info=YOLOModelInfo(),
    )

    process_recording_folder(
        recording_processing_parameter_model=yolo_processing_parameters,
        kill_event=None,
        logging_queue=None,
    )

if __name__ == "__main__":
    recording_folder = Path("/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/")
    process_videos_YOLO(recording_folder=recording_folder)
