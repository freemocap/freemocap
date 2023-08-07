import itertools
import logging
from pathlib import Path
from typing import Tuple, Union
import numpy as np
from matplotlib import pyplot as plt

from freemocap.core_processes.capture_volume_calibration.triangulate_3d_data import (
    triangulate_3d_data,
)
from freemocap.core_processes.capture_volume_calibration.save_mediapipe_3d_data_to_npy import \
    save_mediapipe_3d_data_to_npy
from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_skeleton_names_and_connections import \
    NUMBER_OF_MEDIAPIPE_BODY_MARKERS

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

    body2d_camera_frame_marker_xy = mediapipe_2d_data[:, :, :NUMBER_OF_MEDIAPIPE_BODY_MARKERS, :2]
    bodyReprojErr_frame_marker = reprojection_error_frame_marker[:, :NUMBER_OF_MEDIAPIPE_BODY_MARKERS]

    filtered_skel3d_frame_marker_xyz = raw_skel3d_frame_marker_xyz.copy()

    # create before plot for debugging
    plot_reprojection_error(
        reprojection_error_frame_marker=bodyReprojErr_frame_marker,
        reprojection_error_threshold=reprojection_error_threshold,
        output_folder_path=output_data_folder_path,
        after_filtering=False
    )

    # create combinations of cameras with 1 camera removed
    total_cameras = body2d_camera_frame_marker_xy.shape[0]
    num_cameras_to_remove = 1
    camera_list = list(range(total_cameras))
    camera_combinations = list(itertools.combinations(camera_list, num_cameras_to_remove))

    frame_numbers_to_be_retriangulated = find_frames_with_reprojection_error_above_limit(
        reprojection_error_threshold=reprojection_error_threshold,
        reprojection_error_frames_markers=bodyReprojErr_frame_marker,
    )
    logger.info(
        f"Found {len(frame_numbers_to_be_retriangulated)} frames with reprojection error above threshold of {reprojection_error_threshold} mm"
    )


    while len(frame_numbers_to_be_retriangulated) > 0:
        # if we've checked all combinations with n cameras removed, start checking with n+1 removed
        if len(camera_combinations) == total_cameras - 2:
            num_cameras_to_remove += 1
            camera_combinations = list(itertools.combinations(camera_list, num_cameras_to_remove))

        # pick a combination of cameras to rerun with
        cameras_to_remove = camera_combinations.pop()

        # don't triangulate with less than 2 cameras
        if len(cameras_to_remove) > total_cameras - 2:
            logging.debug(
                f"There are still {len(frame_numbers_to_be_retriangulated)} frames with reprojection error above threshold with all camera combinations, converting data for those frames to NaNs"
            )
            filtered_skel3d_frame_marker_xyz[frame_numbers_to_be_retriangulated, :, :] = np.nan
            bodyReprojErr_frame_marker[frame_numbers_to_be_retriangulated, :] = np.nan
            break

        logging.debug(f"Retriangulating without cameras {cameras_to_remove}")
        data_to_reproject_camera_frame_marker_xy = set_unincluded_data_to_nans(
            mediapipe_2d_data=body2d_camera_frame_marker_xy,
            frames_with_reprojection_error=frame_numbers_to_be_retriangulated,
            cameras_to_remove=cameras_to_remove,
        )

        retriangulated_data_frame_marker_xyz, new_reprojection_error = triangulate_3d_data(
            anipose_calibration_object=anipose_calibration_object,
            mediapipe_2d_data=data_to_reproject_camera_frame_marker_xy,
            output_data_folder_path=output_data_folder_path,
            use_triangulate_ransac=use_triangulate_ransac,
        )

        logging.debug("Putting retriangulated data back into full session data")
        bodyReprojErr_frame_marker[frame_numbers_to_be_retriangulated, :] = new_reprojection_error

        filtered_skel3d_frame_marker_xyz[frame_numbers_to_be_retriangulated, :NUMBER_OF_MEDIAPIPE_BODY_MARKERS, :] = retriangulated_data_frame_marker_xyz

        frame_numbers_to_be_retriangulated = find_frames_with_reprojection_error_above_limit(
            reprojection_error_threshold=reprojection_error_threshold,
            reprojection_error_frames_markers=bodyReprojErr_frame_marker,
        )
        logging.debug(f"There are now {len(frame_numbers_to_be_retriangulated)} frames with reprojection error above threshold")

    plot_reprojection_error(
        reprojection_error_frame_marker=reprojection_error_frame_marker,
        reprojection_error_threshold=bodyReprojErr_frame_marker,
        output_folder_path=output_data_folder_path,
        after_filtering=True
    )

    filtered_reprojection_error_frame_marker = reprojection_error_frame_marker.copy()
    filtered_reprojection_error_frame_marker[:, :NUMBER_OF_MEDIAPIPE_BODY_MARKERS] = bodyReprojErr_frame_marker

    return (filtered_skel3d_frame_marker_xyz, filtered_reprojection_error_frame_marker)


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
    data_to_reproject = mediapipe_2d_data[:, frames_with_reprojection_error, :, :]
    data_to_reproject[cameras_to_remove, :, :, :] = np.nan
    return data_to_reproject


def plot_reprojection_error(
    reprojection_error_frame_marker: np.ndarray,
    reprojection_error_threshold: float,
    output_folder_path: Union[str, Path],
    after_filtering: bool = False,
) -> None:

    title = "Mean Reprojection Error Per Frame"
    file_name = "debug_reprojection_error_filtering.png"
    output_filepath = Path(output_folder_path) / file_name
    mean_reprojection_error_per_frame = np.nanmean(
        reprojection_error_frame_marker,
        axis=1,
    )
    if after_filtering:
        plt.plot(mean_reprojection_error_per_frame, color="orange", alpha=0.9, label="Data After Filtering")
        plt.xlabel("Frame")
        plt.ylabel("Mean Reprojection Error Across Markers (mm)")
        plt.hlines(y=reprojection_error_threshold, xmin=0, xmax=len(mean_reprojection_error_per_frame), color="red", label="Cutoff Threshold")
        plt.title(title)
        plt.legend(loc="upper right")
        logger.info(f"Saving debug plots to: {output_filepath}")
        plt.savefig(output_filepath, dpi=300)
    else:
        plt.plot(mean_reprojection_error_per_frame, color="blue", label="Data Before Filtering")

