from pathlib import Path
from skellytracker.trackers.mediapipe_tracker.__mediapipe_tracker import (
    MediapipeTracker,
    MediapipeTrackerConfig
)

from skellyforge.triangulation.load_camera_group import load_camera_group_from_toml
from skellyforge.triangulation.triangulate import (
    TriangulationConfig,
    triangulate_dict,
)
from skellyforge.calibration.freemocap_anipose import CameraGroup
from skellyforge.data_models.data_3d import Trajectory3d

from skellyforge.post_processing.interpolation.apply_interpolation import interpolate_trajectory
from skellyforge.post_processing.interpolation.interpolation_config import InterpolationConfig,InterpolationMethod

from skellyforge.post_processing.filters.apply_filter import filter_trajectory
from skellyforge.post_processing.filters.filter_config import FilterConfig, FilterMethod

from skellyforge.skellymodels.managers.human import Human

import cv2 
import logging 
from tqdm import tqdm


### WHAT THIS PIPELINE CAN DO:
# - take in a folder of synchronized videos, run skellytracker's mediapipe tracker, triangulate, post-process, and save out the final data in various formats
# - currently hardcoded for the MediaPipe tracker and MediaPipeModelInfo for this run
# - has a Pydantic config for each major step (pose estimation, triangulation, interpolation, filtering) that can be modified when calling the pipeline

### WHAT IT CANT DO CURRENTLY:
# - save out intermediate data (2D data from pose estimation, raw 3D triangulated data) - can easily add an np.save, but unsure of the format we want the 2d data saved as
# - multiprocessing on the pose estimation step
# - load from disk 
# - annotated video saving out 


def process_video(tracker:MediapipeTracker, path_to_video:str|Path):
    cap = cv2.VideoCapture(str(path_to_video))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_number = 0

    with tqdm(total=total_frames, desc=f"Processing {path_to_video.name}", unit="frame") as pbar:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            tracker.process_image(frame_number=frame_number, image=frame)
            frame_number += 1
            pbar.update(1)  

    cap.release()
 

def run_pipeline(path_to_synchronized_video_folder: Path|str,
                 path_to_calibration_toml: Path|str,
                 path_to_output_data_folder: Path|str,
                 triangulation_config: TriangulationConfig,
                 interp_config: InterpolationConfig,
                 filter_config: FilterConfig,
                 mediapipe_config: MediapipeTrackerConfig|None = None,
                 ):
    
    Path(path_to_output_data_folder).mkdir(parents=True, exist_ok=True) #create the 'mediapipe' specific folder in the output data folder


    path_to_synchronized_video_folder = Path(path_to_synchronized_video_folder)
    video_list = list(path_to_synchronized_video_folder.glob("*.mp4"))
    print(f"Found {len(video_list)} videos to process.")
    tracker_output = {}

    for video_path in video_list:
        tracker = MediapipeTracker.create(config=mediapipe_config)
        process_video(tracker=tracker,
                      path_to_video=video_path)
        data_2d_xyc = tracker.recorder.to_array.copy()
        tracker_output[video_path.stem] = data_2d_xyc[..., :2] 

    print(f"2D data shape: {data_2d_xyc.shape}") 

    camera_group:CameraGroup = load_camera_group_from_toml(path_to_calibration_toml)

    raw_trajectory_3d: Trajectory3d = triangulate_dict(
        data_dict=tracker_output,
        camera_group=camera_group,
        config=triangulation_config,
    )

    interpolated_trajectory_3d: Trajectory3d = interpolate_trajectory(
        trajectory=raw_trajectory_3d,
        config=interp_config
    )

    filtered_trajectory_3d: Trajectory3d = filter_trajectory(
        trajectory=interpolated_trajectory_3d,
        config=filter_config
    )
    
    skellymodel:Human = Human.from_tracked_points_numpy_array( #name/model info are hardcoded - but ideally we'll make a some sort of config that we'll pull from to choose these
        name = "human",
        model_info= MediapipeModelInfo(),
        tracked_points_numpy_array=filtered_trajectory_3d.triangulated_data,
    )

    skellymodel.put_skeleton_on_ground()
    skellymodel.fix_hands_to_wrist()
    skellymodel.calculate()

    skellymodel.save_out_numpy_data(path_to_output_data_folder)
    skellymodel.save_out_csv_data(path_to_output_data_folder)
    skellymodel.save_out_all_data_csv(path_to_output_data_folder)
    skellymodel.save_out_all_data_parquet(path_to_output_data_folder)
    skellymodel.save_out_all_xyz_numpy_data(path_to_output_data_folder)

    f = 2
    

if __name__ == '__main__':
    from skellytracker.trackers.mediapipe_tracker.__mediapipe_tracker import MediapipeTrackerConfig
    from skellyforge.skellymodels.models.tracking_model_info import MediapipeModelInfo

    path_to_recording = Path(r"C:\Users\aaron\freemocap_data\recording_sessions\freemocap_test_data")

    mediapipe_config = MediapipeTrackerConfig()
    triangulation_config = TriangulationConfig(
        use_ransac=False
    )

    interp_config = InterpolationConfig(
        method=InterpolationMethod.linear,
    )

    filter_config = FilterConfig(
        method=FilterMethod.butter_low_pass,
        cutoff=6.0,
        sampling_rate=30.0,
        order=4
    )

    path_to_synchronized_video_folder = path_to_recording / "synchronized_videos"
    path_to_calibration_toml = list(path_to_recording.glob("*_camera_calibration.toml"))[0] #if you want to auto find the calibration file in the recording folder, otherwise just hardcode it here
    path_to_output_data_folder = path_to_recording / "output_data"/ "mediapipe" #NOTE: creating a mediapipe specific folder to add the data into 


    run_pipeline(path_to_synchronized_video_folder=path_to_synchronized_video_folder,
                 path_to_calibration_toml=path_to_calibration_toml,
                 mediapipe_config=mediapipe_config,
                 triangulation_config=triangulation_config,
                 interp_config=interp_config,
                 filter_config=filter_config,
                 path_to_output_data_folder=path_to_output_data_folder
                 )
