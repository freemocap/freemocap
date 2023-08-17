import logging
from pathlib import Path
from typing import Tuple, Union
from matplotlib import pyplot as plt
import numpy as np
from freemocap.core_processes.capture_volume_calibration.triangulate_3d_data import triangulate_3d_data

from freemocap.core_processes.detecting_things_in_2d_images.mediapipe_stuff.data_models.mediapipe_skeleton_names_and_connections import (
    NUMBER_OF_MEDIAPIPE_BODY_MARKERS,
)

logger = logging.getLogger(__name__)


def filter_by_reprojection_error(
    reprojection_error_camera_frame_marker: np.ndarray,
    reprojection_error_frame_marker: np.ndarray,
    reprojection_error_confidence_threshold: float,
    mediapipe_2d_data: np.ndarray,
    raw_skel3d_frame_marker_xyz: np.ndarray,
    anipose_calibration_object,
    output_data_folder_path: Union[str, Path],
    use_triangulate_ransac: bool = False,
    minimum_cameras_to_reproject: int = 2,
) -> Tuple[np.ndarray, np.ndarray]:
    body2d_camera_frame_marker_xy = mediapipe_2d_data[:, :, :NUMBER_OF_MEDIAPIPE_BODY_MARKERS, :2]
    bodyReprojErr_camera_frame_marker = reprojection_error_camera_frame_marker[:, :, :NUMBER_OF_MEDIAPIPE_BODY_MARKERS]

    if reprojection_error_confidence_threshold > 100:
        reprojection_error_confidence_threshold = 100
    if reprojection_error_confidence_threshold < 0:
        reprojection_error_confidence_threshold = 0

    reprojection_error_threshold = np.nanpercentile(
        bodyReprojErr_camera_frame_marker, reprojection_error_confidence_threshold
    )

    # create before plot for debugging
    plot_reprojection_error(
        reprojection_error_frame_marker=reprojection_error_frame_marker,
        reprojection_error_threshold=reprojection_error_threshold,
        output_folder_path=output_data_folder_path,
        after_filtering=False,
    )

    indices_above_threshold = np.nonzero(bodyReprojErr_camera_frame_marker > reprojection_error_threshold)

    unique_frame_marker_list = get_unique_frame_marker_list(indices_above_threshold=indices_above_threshold)
    logger.info(f"number of frame/marker combos with reprojection error above threshold: {len(unique_frame_marker_list)}")

    # this can be "while len(unique_frame_marker_list) > 0..."
    (cameras_to_remove, frames_to_reproject, markers_to_reproject) = get_camera_frame_marker_lists_to_reproject(
        reprojError_cam_frame_marker=bodyReprojErr_camera_frame_marker,
        frame_marker_list=unique_frame_marker_list,
    )

    data_to_reproject_camera_frame_marker_xy = set_unincluded_data_to_nans(
        mediapipe_2d_data=body2d_camera_frame_marker_xy,
        frames_with_reprojection_error=frames_to_reproject,
        markers_with_reprojection_error=markers_to_reproject,
        cameras_to_remove=cameras_to_remove,
    )

    (
        retriangulated_data_frame_marker_xyz,
        new_reprojection_error_flat,
        new_reprojError_cam_frame_marker,
    ) = triangulate_3d_data(
        anipose_calibration_object=anipose_calibration_object,
        mediapipe_2d_data=data_to_reproject_camera_frame_marker_xy,
        use_triangulate_ransac=use_triangulate_ransac,
    )

    plot_reprojection_error(
        reprojection_error_frame_marker=new_reprojection_error_flat,
        reprojection_error_threshold=reprojection_error_threshold,
        output_folder_path=output_data_folder_path,
        after_filtering=True,
    )

    indices_above_threshold = np.nonzero(new_reprojError_cam_frame_marker > reprojection_error_threshold)

    unique_frame_marker_list = get_unique_frame_marker_list(indices_above_threshold=indices_above_threshold)
    logger.info(f"number of frame/marker combos with reprojection error above threshold after filtering: {len(unique_frame_marker_list)}")

    # put retriangulated data back in place
    filtered_skel3d_frame_marker_xyz = raw_skel3d_frame_marker_xyz.copy()
    filtered_skel3d_frame_marker_xyz[:, :NUMBER_OF_MEDIAPIPE_BODY_MARKERS, :] = retriangulated_data_frame_marker_xyz

    filtered_reprojection_error_frame_marker = reprojection_error_frame_marker.copy()
    filtered_reprojection_error_frame_marker[:, :NUMBER_OF_MEDIAPIPE_BODY_MARKERS] = new_reprojection_error_flat

    filtered_reprojection_error_camera_frame_marker = reprojection_error_camera_frame_marker.copy()
    filtered_reprojection_error_camera_frame_marker[:, :, :NUMBER_OF_MEDIAPIPE_BODY_MARKERS] = new_reprojError_cam_frame_marker

    return (
        filtered_skel3d_frame_marker_xyz,
        filtered_reprojection_error_frame_marker,
        filtered_reprojection_error_camera_frame_marker,
    )


def get_unique_frame_marker_list(
    indices_above_threshold: np.ndarray,
) -> list:
    return list(set(zip(indices_above_threshold[1], indices_above_threshold[2])))

def get_camera_frame_marker_lists_to_reproject(
    reprojError_cam_frame_marker: np.ndarray, frame_marker_list: list
) -> Tuple[list, list, list]:
    cameras_to_remove = []
    frames_to_reproject = []
    markers_to_reproject = []
    for frame, marker in frame_marker_list:
        frames_to_reproject.append(frame)
        markers_to_reproject.append(marker)
        max_index = reprojError_cam_frame_marker[:, frame, marker].argmax()
        cameras_to_remove.append([max_index])
    return (cameras_to_remove, frames_to_reproject, markers_to_reproject)


def set_unincluded_data_to_nans(
    mediapipe_2d_data: np.ndarray,
    frames_with_reprojection_error: list,
    markers_with_reprojection_error: list,
    cameras_to_remove: list[int],
) -> np.ndarray:
    data_to_reproject = mediapipe_2d_data.copy()
    for camera, frame, marker in zip(
        cameras_to_remove, frames_with_reprojection_error, markers_with_reprojection_error
    ):
        data_to_reproject[camera, frame, marker, :] = np.nan
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
        plt.ylim(0, 2 * reprojection_error_threshold)
        plt.hlines(
            y=reprojection_error_threshold,
            xmin=0,
            xmax=len(mean_reprojection_error_per_frame),
            color="red",
            label="Cutoff Threshold",
        )
        plt.title(title)
        plt.legend(loc="upper right")
        logger.info(f"Saving debug plots to: {output_filepath}")
        plt.savefig(output_filepath, dpi=300)
    else:
        plt.plot(mean_reprojection_error_per_frame, color="blue", label="Data Before Filtering")

