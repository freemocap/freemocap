from dataclasses import dataclass
import pandas as pd

from freemocap_web.core.project import Project
from freemocap_web.core.mediapipe.skeleton_detector import MediaPipeSkeletonDetector
from freemocap_web.core.post_process import process_single_camera_skeleton_data, skeleton
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.convert_mediapipe_npy_to_csv import \
    convert_mediapipe_npy_to_csv
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_skeleton_names_and_connections import \
    mediapipe_names_and_connections_dict

from freemocap.core_processes.post_process_skeleton_data.calculate_center_of_mass import run_center_of_mass_calculations
from freemocap.core_processes.post_process_skeleton_data.estimate_skeleton_segment_lengths import \
    estimate_skeleton_segment_lengths, mediapipe_skeleton_segment_definitions
from freemocap.core_processes.post_process_skeleton_data.post_process_skeleton import save_skeleton_array_to_npy
from freemocap.data_layer.data_saver.data_saver import DataSaver
from freemocap.utilities.geometry.rotate_by_90_degrees_around_x_axis import rotate_by_90_degrees_around_x_axis
from freemocap.utilities.save_dictionary_to_json import save_dictionary_to_json


@dataclass
class MediapipeImageData:
    Project: Project
    MediaPipeSkeletonDetector: MediaPipeSkeletonDetector
    mediapipe_image_data_raw: any
    raw_skel3d_frame_marker_xyz: any
    skeleton_reprojection_error_fr_mar: any
    rotated_raw_skel3d_frame_marker_xyz: any
    skel3d_frame_marker_xyz: any
    segment_COM_frame_imgPoint_XYZ: any
    totalBodyCOM_frame_XYZ: any
    path_to_skeleton_body_csv: any
    skeleton_dataframe: pd.DataFrame
    skeleton_segment_lengths_dict: any
    DataSaver: DataSaver

    @staticmethod
    def from_project(project: Project):
        mediapipe_skeleton_detector = MediaPipeSkeletonDetector(
            parameter_model=project.Config.MediaPipe,
            use_tqdm=project.Config.use_tqdm
        )

        mediapipe_image_data_raw = mediapipe_skeleton_detector.process_folder_full_of_videos(
            path_to_folder_of_videos_to_process=project.Folders.SyncVideos,
            output_data_folder_path=project.Folders.MediaPipeData,
            annotated_video_path=project.Folders.Annotated,
            use_multiprocessing=project.Config.MediaPipe.use_multiprocessing)

        raw_skel3d_frame_marker_xyz, skeleton_reprojection_error_fr_mar = process_single_camera_skeleton_data(
            input_image_data_frame_marker_xyz=mediapipe_image_data_raw[0],
            raw_data_folder_path=project.Folders.MediaPipeData)

        rotated_raw_skel3d_frame_marker_xyz = rotate_by_90_degrees_around_x_axis(raw_skel3d_frame_marker_xyz)

        skel3d_frame_marker_xyz = skeleton.post_process_data(
            post_processing_config=project.Config.PostProcessing,
            raw_skel3d_frame_marker_xyz=rotated_raw_skel3d_frame_marker_xyz)

        save_skeleton_array_to_npy(
            array_to_save=skel3d_frame_marker_xyz,
            skeleton_file_name="mediaPipeSkel_3d_body_hands_face.npy",
            path_to_folder_where_we_will_save_this_data=project.Folders.OutputData)

        segment_com_frame_img_point_xyz, total_body_com_frame_xyz = run_center_of_mass_calculations(
            processed_skel3d_frame_marker_xyz=skel3d_frame_marker_xyz)

        save_skeleton_array_to_npy(
            array_to_save=segment_com_frame_img_point_xyz,
            skeleton_file_name="segmentCOM_frame_joint_xyz.npy",
            path_to_folder_where_we_will_save_this_data=project.Folders.OutputData / "center_of_mass")

        save_skeleton_array_to_npy(
            array_to_save=total_body_com_frame_xyz,
            skeleton_file_name="total_body_center_of_mass_xyz.npy",
            path_to_folder_where_we_will_save_this_data=project.Folders.OutputData / "center_of_mass")

        convert_mediapipe_npy_to_csv(
            mediapipe_3d_frame_trackedPoint_xyz=skel3d_frame_marker_xyz,
            output_data_folder_path=project.Folders.OutputData)

        path_to_skeleton_body_csv = project.Folders.OutputData / "mediapipe_body_3d_xyz.csv"

        skeleton_dataframe = pd.read_csv(path_to_skeleton_body_csv)

        skeleton_segment_lengths_dict = estimate_skeleton_segment_lengths(
            skeleton_dataframe=skeleton_dataframe,
            skeleton_segment_definitions=mediapipe_skeleton_segment_definitions)

        save_dictionary_to_json(
            save_path=project.Folders.OutputData,
            file_name="mediapipe_skeleton_segment_lengths.json",
            dictionary=skeleton_segment_lengths_dict)

        save_dictionary_to_json(
            save_path=project.Folders.OutputData,
            file_name="mediapipe_names_and_connections_dict.json",
            dictionary=mediapipe_names_and_connections_dict)

        data_saver = DataSaver(recording_folder_path=project.Folders.Root)
        data_saver.save_all()

        return MediapipeImageData(
            Project=project,
            MediaPipeSkeletonDetector=mediapipe_skeleton_detector,
            mediapipe_image_data_raw=mediapipe_image_data_raw,
            raw_skel3d_frame_marker_xyz=raw_skel3d_frame_marker_xyz,
            skeleton_reprojection_error_fr_mar=skeleton_reprojection_error_fr_mar,
            rotated_raw_skel3d_frame_marker_xyz=rotated_raw_skel3d_frame_marker_xyz,
            skel3d_frame_marker_xyz=skel3d_frame_marker_xyz,
            segment_COM_frame_imgPoint_XYZ=segment_com_frame_img_point_xyz,
            totalBodyCOM_frame_XYZ=total_body_com_frame_xyz,
            path_to_skeleton_body_csv=path_to_skeleton_body_csv,
            skeleton_dataframe=skeleton_dataframe,
            skeleton_segment_lengths_dict=skeleton_segment_lengths_dict,
            DataSaver=data_saver)
