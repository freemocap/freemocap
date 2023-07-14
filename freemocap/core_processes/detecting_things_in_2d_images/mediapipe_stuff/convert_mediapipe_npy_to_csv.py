# %%
import logging
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd
from mediapipe.python.solutions import holistic as mp_holistic

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    MEDIAPIPE_RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME,
    MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME,
    MEDIAPIPE_LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME,
)

logger = logging.getLogger(__name__)


def convert_mediapipe_npy_to_csv(
    mediapipe_3d_frame_trackedPoint_xyz: np.ndarray,
    output_data_folder_path: Union[str, Path],
):
    logger.info(
        f"Converting npy data with shape: {mediapipe_3d_frame_trackedPoint_xyz.shape} into `csv` and smaller `npy` files"
    )

    # %%
    mediapipe_pose_landmark_names = [landmark.name.lower() for landmark in mp_holistic.PoseLandmark]
    mediapipe_hand_landmark_names = [landmark.name.lower() for landmark in mp_holistic.HandLandmark]
    # face_landmark_names = [landmark.name.lower() for landmark in mp_holistic.PoseLandmark] #gonna have the clever for the face
    # logger.info(f"Body tracked point names: {mediapipe_pose_landmark_names}")
    # logger.info(mediapipe_hand_landmark_names)

    # %%
    # get number of points in body, hands, face

    number_of_body_points = len(mediapipe_pose_landmark_names)
    number_of_hand_points = len(mediapipe_hand_landmark_names)

    first_body_marker_index = 0
    last_body_marker_index = number_of_body_points - 1

    first_right_hand_marker_index = last_body_marker_index + 1
    last_right_hand_marker_index = number_of_body_points + number_of_hand_points - 1

    first_left_hand_marker_index = last_right_hand_marker_index + 1
    last_left_hand_marker_index = last_right_hand_marker_index + 1 + number_of_hand_points - 1

    first_face_marker_index = last_left_hand_marker_index + 1
    last_face_marker_index = mediapipe_3d_frame_trackedPoint_xyz.shape[1]

    number_of_face_points = last_face_marker_index - first_face_marker_index

    # logger.info(
    #     f"body tracked point indices: {first_body_marker_index}:{last_body_marker_index}"
    # )
    # logger.info(
    #     f"right hand tracked point indices: {first_right_hand_marker_index}:{last_right_hand_marker_index}"
    # )
    # logger.info(
    #     f"left hand tracked point indices: {first_left_hand_marker_index}:{last_left_hand_marker_index}"
    # )
    # logger.info(
    #     f"face tracked point indices: {first_face_marker_index}:{last_face_marker_index}"
    # )
    #
    # logger.info(
    #     f"number of body points: {last_body_marker_index - first_body_marker_index + 1}"
    # )
    # logger.info(
    #     f"number of right hand points: {last_right_hand_marker_index - first_right_hand_marker_index + 1}"
    # )
    # logger.info(
    #     f"number of left hand points: {last_left_hand_marker_index - first_left_hand_marker_index + 1}"
    # )
    # logger.info(
    #     f"number of face points: {last_face_marker_index - first_face_marker_index + 1}"
    # )

    # %%
    body_3d_xyz = mediapipe_3d_frame_trackedPoint_xyz[:, first_body_marker_index : last_body_marker_index + 1, :]
    right_hand_3d_xyz = mediapipe_3d_frame_trackedPoint_xyz[
        :, first_right_hand_marker_index : last_right_hand_marker_index + 1, :
    ]
    left_hand_3d_xyz = mediapipe_3d_frame_trackedPoint_xyz[
        :, first_left_hand_marker_index : last_left_hand_marker_index + 1, :
    ]
    face_3d_xyz = mediapipe_3d_frame_trackedPoint_xyz[:, first_face_marker_index : last_face_marker_index + 1, :]

    # logger.info(f"body 3d xyz shape: {body_3d_xyz.shape}")
    # logger.info(f"right hand 3d xyz shape: {right_hand_3d_xyz.shape}")
    # logger.info(f"left hand 3d xyz shape: {left_hand_3d_xyz.shape}")
    # logger.info(f"face 3d xyz shape: {face_3d_xyz.shape}")

    # %%
    # save broken up npy files
    np.save(str(Path(output_data_folder_path) / "mediapipe_body_3d_xyz.npy"), body_3d_xyz)
    np.save(
        str(Path(output_data_folder_path) / "mediapipe_right_hand_3d_xyz.npy"),
        right_hand_3d_xyz,
    )
    np.save(
        str(Path(output_data_folder_path) / "mediapipe_left_hand_3d_xyz.npy"),
        left_hand_3d_xyz,
    )
    np.save(str(Path(output_data_folder_path) / "mediapipe_face_3d_xyz.npy"), face_3d_xyz)

    # %%
    # create pandas data frame headers

    body_3d_xyz_header = []
    for landmark_name in mediapipe_pose_landmark_names:
        body_3d_xyz_header.append(f"{landmark_name}_x")
        body_3d_xyz_header.append(f"{landmark_name}_y")
        body_3d_xyz_header.append(f"{landmark_name}_z")

    right_hand_3d_xyz_header = []
    for landmark_name in mediapipe_hand_landmark_names:
        right_hand_3d_xyz_header.append(f"right_hand_{landmark_name}_x")
        right_hand_3d_xyz_header.append(f"right_hand_{landmark_name}_y")
        right_hand_3d_xyz_header.append(f"right_hand_{landmark_name}_z")

    left_hand_3d_xyz_header = []
    for landmark_name in mediapipe_hand_landmark_names:
        left_hand_3d_xyz_header.append(f"left_hand_{landmark_name}_x")
        left_hand_3d_xyz_header.append(f"left_hand_{landmark_name}_y")
        left_hand_3d_xyz_header.append(f"left_hand_{landmark_name}_z")

    face_3d_xyz_header = []
    for landmark_number in range(last_face_marker_index - first_face_marker_index):
        face_3d_xyz_header.append(f"face_{str(landmark_number).zfill(4)}_x")
        face_3d_xyz_header.append(f"face_{str(landmark_number).zfill(4)}_y")
        face_3d_xyz_header.append(f"face_{str(landmark_number).zfill(4)}_z")
    #
    # logger.debug(
    #     f"length of body 3d xyz header: {len(body_3d_xyz_header)}, should be: {number_of_body_points * 3}"
    # )
    # logger.debug(
    #     f"length of right hand 3d xyz header: {len(right_hand_3d_xyz_header)}, should be: {number_of_hand_points * 3}"
    # )
    # logger.debug(
    #     f"length of left hand 3d xyz header: {len(left_hand_3d_xyz_header)}, should be: {number_of_hand_points * 3}"
    # )
    # logger.debug(
    #     f"length of face 3d xyz header: {len(face_3d_xyz_header)}, should be: {number_of_face_points * 3}"
    # )

    # %%
    number_of_frames = mediapipe_3d_frame_trackedPoint_xyz.shape[0]
    body_flat = body_3d_xyz.reshape(number_of_frames, number_of_body_points * 3)

    body_dataframe = pd.DataFrame(body_flat, columns=body_3d_xyz_header)
    body_dataframe.to_csv(str(Path(output_data_folder_path) / MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME), index=False)

    right_hand_flat = right_hand_3d_xyz.reshape(number_of_frames, number_of_hand_points * 3)
    right_hand_dataframe = pd.DataFrame(right_hand_flat, columns=right_hand_3d_xyz_header)
    right_hand_dataframe.to_csv(
        str(Path(output_data_folder_path) / MEDIAPIPE_RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME),
        index=False,
    )

    left_hand_flat = left_hand_3d_xyz.reshape(number_of_frames, number_of_hand_points * 3)
    left_hand_dataframe = pd.DataFrame(left_hand_flat, columns=left_hand_3d_xyz_header)
    left_hand_dataframe.to_csv(
        str(Path(output_data_folder_path) / MEDIAPIPE_LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME),
        index=False,
    )

    face_flat = face_3d_xyz.reshape(number_of_frames, number_of_face_points * 3)
    face_dataframe = pd.DataFrame(face_flat, columns=face_3d_xyz_header)
    face_dataframe.to_csv(str(Path(output_data_folder_path) / "mediapipe_face_3d_xyz.csv"), index=False)

    # %%

    # %%
    mediapipe_pose_landmark_names = [landmark.name.lower() for landmark in mp_holistic.PoseLandmark]
    mediapipe_hand_landmark_names = [landmark.name.lower() for landmark in mp_holistic.HandLandmark]
    # face_landmark_names = [landmark.name.lower() for landmark in mp_holistic.PoseLandmark] #gonna have the clever for the face

    # logger.debug(f"Body tracked point names: {mediapipe_pose_landmark_names}")
    # logger.debug(mediapipe_hand_landmark_names)

    # %%
    # get number of points in body, hands, face

    number_of_body_points = len(mediapipe_pose_landmark_names)
    number_of_hand_points = len(mediapipe_hand_landmark_names)

    first_body_marker_index = 0
    last_body_marker_index = number_of_body_points - 1

    first_right_hand_marker_index = last_body_marker_index + 1
    last_right_hand_marker_index = number_of_body_points + number_of_hand_points - 1

    first_left_hand_marker_index = last_right_hand_marker_index + 1
    last_left_hand_marker_index = last_right_hand_marker_index + 1 + number_of_hand_points - 1

    first_face_marker_index = last_left_hand_marker_index + 1
    last_face_marker_index = mediapipe_3d_frame_trackedPoint_xyz.shape[1]

    number_of_face_points = last_face_marker_index - first_face_marker_index

    # logger.debug(
    #     f"body tracked point indices: {first_body_marker_index}:{last_body_marker_index}"
    # )
    # logger.debug(
    #     f"right hand tracked point indices: {first_right_hand_marker_index}:{last_right_hand_marker_index}"
    # )
    # logger.debug(
    #     f"left hand tracked point indices: {first_left_hand_marker_index}:{last_left_hand_marker_index}"
    # )
    # logger.debug(
    #     f"face tracked point indices: {first_face_marker_index}:{last_face_marker_index}"
    # )
    #
    # logger.debug(
    #     f"number of body points: {last_body_marker_index - first_body_marker_index + 1}"
    # )
    # logger.debug(
    #     f"number of right hand points: {last_right_hand_marker_index - first_right_hand_marker_index + 1}"
    # )
    # logger.debug(
    #     f"number of left hand points: {last_left_hand_marker_index - first_left_hand_marker_index + 1}"
    # )
    # logger.debug(
    #     f"number of face points: {last_face_marker_index - first_face_marker_index + 1}"
    # )

    # %%
    body_3d_xyz = mediapipe_3d_frame_trackedPoint_xyz[:, first_body_marker_index : last_body_marker_index + 1, :]
    right_hand_3d_xyz = mediapipe_3d_frame_trackedPoint_xyz[
        :, first_right_hand_marker_index : last_right_hand_marker_index + 1, :
    ]
    left_hand_3d_xyz = mediapipe_3d_frame_trackedPoint_xyz[
        :, first_left_hand_marker_index : last_left_hand_marker_index + 1, :
    ]
    face_3d_xyz = mediapipe_3d_frame_trackedPoint_xyz[:, first_face_marker_index : last_face_marker_index + 1, :]

    logger.debug(f"body 3d xyz shape: {body_3d_xyz.shape}")
    logger.debug(f"right hand 3d xyz shape: {right_hand_3d_xyz.shape}")
    logger.debug(f"left hand 3d xyz shape: {left_hand_3d_xyz.shape}")
    logger.debug(f"face 3d xyz shape: {face_3d_xyz.shape}")

    # %%
    # save broken up npy files
    np.save(str(Path(output_data_folder_path) / "mediapipe_body_3d_xyz.npy"), body_3d_xyz)
    np.save(
        str(Path(output_data_folder_path) / "mediapipe_right_hand_3d_xyz.npy"),
        right_hand_3d_xyz,
    )
    np.save(
        str(Path(output_data_folder_path) / "mediapipe_left_hand_3d_xyz.npy"),
        left_hand_3d_xyz,
    )
    np.save(str(Path(output_data_folder_path) / "mediapipe_face_3d_xyz.npy"), face_3d_xyz)

    # %%
    # create pandas data frame headers

    body_3d_xyz_header = []
    for landmark_name in mediapipe_pose_landmark_names:
        body_3d_xyz_header.append(f"{landmark_name}_x")
        body_3d_xyz_header.append(f"{landmark_name}_y")
        body_3d_xyz_header.append(f"{landmark_name}_z")

    right_hand_3d_xyz_header = []
    for landmark_name in mediapipe_hand_landmark_names:
        right_hand_3d_xyz_header.append(f"right_hand_{landmark_name}_x")
        right_hand_3d_xyz_header.append(f"right_hand_{landmark_name}_y")
        right_hand_3d_xyz_header.append(f"right_hand_{landmark_name}_z")

    left_hand_3d_xyz_header = []
    for landmark_name in mediapipe_hand_landmark_names:
        left_hand_3d_xyz_header.append(f"left_hand_{landmark_name}_x")
        left_hand_3d_xyz_header.append(f"left_hand_{landmark_name}_y")
        left_hand_3d_xyz_header.append(f"left_hand_{landmark_name}_z")

    face_3d_xyz_header = []
    for landmark_number in range(last_face_marker_index - first_face_marker_index):
        face_3d_xyz_header.append(f"face_{str(landmark_number).zfill(4)}_x")
        face_3d_xyz_header.append(f"face_{str(landmark_number).zfill(4)}_y")
        face_3d_xyz_header.append(f"face_{str(landmark_number).zfill(4)}_z")

    logger.debug(
        f"length of body 3d xyz `.csv` header: {len(body_3d_xyz_header)}, should be: {number_of_body_points * 3}"
    )
    logger.debug(
        f"length of right hand 3d xyz `.csv` header: {len(right_hand_3d_xyz_header)}, should be: {number_of_hand_points * 3}"
    )
    logger.debug(
        f"length of left hand 3d xyz `.csv` header: {len(left_hand_3d_xyz_header)}, should be: {number_of_hand_points * 3}"
    )
    logger.debug(
        f"length of face 3d xyz `.csv` header: {len(face_3d_xyz_header)}, should be: {number_of_face_points * 3}"
    )

    # %%
    number_of_frames = mediapipe_3d_frame_trackedPoint_xyz.shape[0]
    body_flat = body_3d_xyz.reshape(number_of_frames, number_of_body_points * 3)

    body_dataframe = pd.DataFrame(body_flat, columns=body_3d_xyz_header)
    body_dataframe.to_csv(str(Path(output_data_folder_path) / MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME), index=False)

    right_hand_flat = right_hand_3d_xyz.reshape(number_of_frames, number_of_hand_points * 3)
    right_hand_dataframe = pd.DataFrame(right_hand_flat, columns=right_hand_3d_xyz_header)
    right_hand_dataframe.to_csv(
        str(Path(output_data_folder_path) / MEDIAPIPE_RIGHT_HAND_3D_DATAFRAME_CSV_FILE_NAME),
        index=False,
    )

    left_hand_flat = left_hand_3d_xyz.reshape(number_of_frames, number_of_hand_points * 3)
    left_hand_dataframe = pd.DataFrame(left_hand_flat, columns=left_hand_3d_xyz_header)
    left_hand_dataframe.to_csv(
        str(Path(output_data_folder_path) / MEDIAPIPE_LEFT_HAND_3D_DATAFRAME_CSV_FILE_NAME),
        index=False,
    )

    face_flat = face_3d_xyz.reshape(number_of_frames, number_of_face_points * 3)
    face_dataframe = pd.DataFrame(face_flat, columns=face_3d_xyz_header)
    face_dataframe.to_csv(str(Path(output_data_folder_path) / "mediapipe_face_3d_xyz.csv"), index=False)

    logger.info("Done saving out `csv` and broken up `npy` files")


if __name__ == "__main__":
    mediapipe_3d_frame_trackedPoint_xyz = np.load(
        r"C:\Users\jonma\freemocap_data\session_10-15-2022-09_50_10\output_data\post_processed_data\mediaPipeSkel_3d_origin_aligned.npy"
    )
    output_data_folder_path = r"C:\Users\jonma\freemocap_data\session_10-15-2022-09_50_10\output_data"

    convert_mediapipe_npy_to_csv(mediapipe_3d_frame_trackedPoint_xyz, output_data_folder_path)
