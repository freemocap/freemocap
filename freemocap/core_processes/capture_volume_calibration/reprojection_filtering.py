import itertools
import logging
from pathlib import Path
from typing import Tuple, Union
import numpy as np
import plotly.express as px

from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.get_anipose_calibration_object import (
    load_anipose_calibration_toml_from_path,
)

from freemocap.core_processes.capture_volume_calibration.triangulate_3d_data import (
    save_mediapipe_3d_data_to_npy,
    triangulate_3d_data,
)
from freemocap.core_processes.post_process_skeleton_data.post_process_skeleton import save_skeleton_array_to_npy

logger = logging.getLogger(__name__)


def filter_by_reprojection_error(
    reprojection_error_frame_marker: np.ndarray,
    reprojection_error_threshold: float,
    mediapipe_2d_data: np.ndarray,
    raw_skel3d_frame_marker_xyz: np.ndarray,
    anipose_calibration_object,
    output_data_folder_path: Union[str, Path],
    use_triangulate_ransac: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    # create combinations of cameras with 1 camera removed
    total_cameras = mediapipe_2d_data.shape[0]
    num_cameras_to_remove = 1
    camera_list = list(range(total_cameras))
    camera_combinations = list(itertools.combinations(camera_list, num_cameras_to_remove))

    frames_above_threshold = find_frames_with_reprojection_error_above_limit(
        reprojection_error_threshold=reprojection_error_threshold,
        reprojection_error_frames_markers=reprojection_error_frame_marker,
    )
    logger.info(
        f"Found {len(frames_above_threshold)} frames with reprojection error above threshold of {reprojection_error_threshold} mm"
    )

    while len(frames_above_threshold) > 0:
        # if we've checked all combinations with n cameras removed, start checking with n+1 removed
        if len(camera_combinations) == total_cameras - 2:
            num_cameras_to_remove += 1
            camera_combinations = list(itertools.combinations(camera_list, num_cameras_to_remove))

        # pick a combination of cameras to rerun with
        cameras_to_remove = camera_combinations.pop()

        # don't triangulate with less that 2 cameras
        if len(cameras_to_remove) > total_cameras - 2:
            logging.info(
                f"There are still {len(frames_above_threshold)} frames with reprojection error above threshold with all camera combinations, converting data for those frames to NaNs"
            )
            # turn 3d data to nans? or 2d to nans and then triangulate?
            # going with 3d to nans for now
            raw_skel3d_frame_marker_xyz[frames_above_threshold, :, :] = np.nan
            reprojection_error_frame_marker[frames_above_threshold, :] = np.nan
            break

        logging.info(f"Retriangulating without cameras {cameras_to_remove}")
        data_to_reproject = set_unincluded_data_to_nans(
            mediapipe_2d_data=mediapipe_2d_data,
            frames_with_reprojection_error=frames_above_threshold,
            cameras_to_remove=cameras_to_remove,
        )
        print(data_to_reproject.shape)

        retriangulated_data, new_reprojection_error = triangulate_3d_data(
            anipose_calibration_object=anipose_calibration_object,
            mediapipe_2d_data=data_to_reproject,
            output_data_folder_path=output_data_folder_path,
            mediapipe_confidence_cutoff_threshold=0.7,
            use_triangulate_ransac=use_triangulate_ransac,
        )

        logging.info("Putting retriangulated data back into full session data")
        reprojection_error_frame_marker[frames_above_threshold, :] = new_reprojection_error
        raw_skel3d_frame_marker_xyz[frames_above_threshold, :, :] = retriangulated_data

        # it's messy that these are saved again, but only a slice is saved in the triangulate function
        # TODO: move the saving outside of the triangulate function (we can save these values after this function)
        save_mediapipe_3d_data_to_npy(
            data3d_numFrames_numTrackedPoints_XYZ=raw_skel3d_frame_marker_xyz,
            data3d_numFrames_numTrackedPoints_reprojectionError=reprojection_error_frame_marker,
            path_to_folder_where_data_will_be_saved=output_data_folder_path,
        )

        frames_above_threshold = find_frames_with_reprojection_error_above_limit(
            reprojection_error_threshold=reprojection_error_threshold,
            reprojection_error_frames_markers=reprojection_error_frame_marker,
        )
        logging.info(f"There are now {len(frames_above_threshold)} frames with reprojection error above threshold")

    return (raw_skel3d_frame_marker_xyz, reprojection_error_frame_marker)


def find_frames_with_reprojection_error_above_limit(
    reprojection_error_threshold: float,
    reprojection_error_frames_markers: np.ndarray,
) -> list:
    mean_reprojection_error_per_frame = np.nanmean(
        reprojection_error_frames_markers,
        axis=1,
    )
    return [
        i
        for i, reprojection_error in enumerate(mean_reprojection_error_per_frame)
        if reprojection_error > reprojection_error_threshold
    ]

def set_unincluded_data_to_nans(
    mediapipe_2d_data: np.ndarray,
    frames_with_reprojection_error: np.ndarray,
    cameras_to_remove: list[int],
) -> np.ndarray:
    data_to_reproject = np.take(mediapipe_2d_data[:, :, :, :2], frames_with_reprojection_error, axis=1)
    for camera_to_remove in cameras_to_remove:
        data_to_reproject[camera_to_remove, :, :, :] = np.nan
    return data_to_reproject



