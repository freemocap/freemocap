from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel


def processing_pipeline_check(processing_parameters: ProcessingParameterModel) -> None:
    """
    Performs checks on the processing parameters to make sure they are valid with the existing data before running the pipeline.
    Raises FileNotFoundError if any of the checks fail.
    """
    status_check_dict = processing_parameters.recording_info_model.status_check
    if not status_check_dict["synchronized_videos_status_check"]:
        raise FileNotFoundError(
            f"Could not find synchronized_videos folder at {processing_parameters.recording_info_model.synchronized_videos_folder_path}"
        )

    if not processing_parameters.tracking_parameters_model.run_image_tracking:
        if not status_check_dict["data2d_status_check"]:
            raise FileNotFoundError(
                f"No 2d data found at: {processing_parameters.recording_info_model.data_2d_npy_file_path}"
            )

    if not processing_parameters.anipose_triangulate_3d_parameters_model.run_3d_triangulation:
        if not status_check_dict["data3d_status_check"] and not status_check_dict["single_video_check"]:
            raise FileNotFoundError(
                f"No 3d data found at: {processing_parameters.recording_info_model.data_3d_npy_file_path}"
            )
    else:
        if not status_check_dict["calibration_toml_check"] and not status_check_dict["single_video_check"]:
            raise FileNotFoundError(
                f"No calibration file found at: {processing_parameters.recording_info_model.calibration_toml_path}"
            )


if __name__ == "__main__":
    recording_info_model = RecordingInfoModel(
        recording_folder_path="/Users/philipqueen/freemocap_data/recording_sessions/freemocap_sample_data"
    )
    processing_parameters = ProcessingParameterModel(recording_info_model=recording_info_model)

    processing_pipeline_check(processing_parameters=processing_parameters)
