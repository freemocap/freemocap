from pathlib import Path

def main():
    try:
        from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel, AniposeTriangulate3DParametersModel, PostProcessingParametersModel
        from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel
        from freemocap.core_processes.process_motion_capture_videos.processing_pipeline_functions.image_tracking_pipeline_functions import run_image_tracking_pipeline
        from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import process_recording_folder

        from skellytracker.process_folder_of_videos import process_folder_of_videos
        from skellytracker.trackers.openpose_tracker.openpose_model_info import OpenPoseModelInfo, OpenPoseTrackingParams
    except ImportError as e:
        if 'ProcessingParameterModel' not in dir() or 'process_folder_of_videos' not in dir() or 'OpenPoseModelInfo' not in dir():
            raise e

    tracker_name = "OpenPoseTracker"
    num_processes = 1

    input_video_folder = Path(r'C:\Users\aaron\FreeMocap_Data\recording_sessions\freemocap_test_data')

    input_video_filepath = input_video_folder / 'synchronized_videos'
    output_json_path = input_video_folder / 'output_data' / 'raw_data' / 'openpose_jsons'
    output_json_path.mkdir(parents=True, exist_ok=True)

    openpose_root_folder_path = r'C:\openpose'


    recording_model = RecordingInfoModel(
        recording_folder_path=input_video_folder,
        active_tracker="openpose"
    )

    openpose_processing_parameters = ProcessingParameterModel(
        recording_info_model= recording_model,
        tracking_parameters_model=OpenPoseTrackingParams(
            openpose_root_folder_path=str(openpose_root_folder_path),
            output_json_path=str(output_json_path),
            track_hands=True,
            track_face=True
        ),
        anipose_triangulate_3d_parameters_model=AniposeTriangulate3DParametersModel(),
        post_processing_parameters_model=PostProcessingParametersModel(),
        tracking_model_info=OpenPoseModelInfo()
    )

    # run_image_tracking_pipeline(
    #     processing_parameters=openpose_processing_parameters,
    #     kill_event=None,
    #     queue=None,
    #     use_tqdm=True
    # )

    process_recording_folder(
        recording_processing_parameter_model=openpose_processing_parameters,
        kill_event=None,
        logging_queue=None,
    )

    # image_data_numCams_numFrames_numTrackedPts_XYZ = process_folder_of_videos(
    #     model_info=openpose_processing_parameters.tracking_model_info,
    #     tracking_params=OpenPoseTrackingParams(
    #         openpose_root_folder_path=str(openpose_root_folder_path),
    #         output_json_path=str(output_json_path),
    #         track_hands=True,
    #         track_face=True
    #     ),
    #     synchronized_video_path=input_video_filepath,
    #     num_processes=num_processes,
    # )

if __name__ == "__main__":
    main()
