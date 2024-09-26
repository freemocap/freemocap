from pathlib import Path

def main():
    try:
        from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel, AniposeTriangulate3DParametersModel, PostProcessingParametersModel
        from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel
        from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import process_recording_folder
        from skellytracker.trackers.openpose_tracker.openpose_model_info import OpenPoseModelInfo, OpenPoseTrackingParams
    except ImportError as e:
        if 'ProcessingParameterModel' not in dir() or 'process_folder_of_videos' not in dir() or 'OpenPoseModelInfo' not in dir():
            raise e



    recording_folder = Path(r'D:\mdn_treadmill_for_testing')
    openpose_root_folder_path = r'C:\openpose'


    recording_model = RecordingInfoModel(
        recording_folder_path=recording_folder,
        active_tracker="openpose"
    )

    openpose_processing_parameters = ProcessingParameterModel(
        recording_info_model= recording_model,
        tracking_parameters_model=OpenPoseTrackingParams(
            # net_resolution="-1x656",
            openpose_root_folder_path=str(openpose_root_folder_path),
            run_image_tracking=True
        ),
        anipose_triangulate_3d_parameters_model=AniposeTriangulate3DParametersModel(),
        post_processing_parameters_model=PostProcessingParametersModel(),
        tracking_model_info=OpenPoseModelInfo()
    )

    process_recording_folder(
        recording_processing_parameter_model=openpose_processing_parameters,
        kill_event=None,
        logging_queue=None,
    )

if __name__ == "__main__":
    main()
