import logging
from pathlib import Path
from typing import Tuple, Union
from matplotlib import pyplot as plt
import numpy as np


from freemocap.core_processes.capture_volume_calibration.save_3d_data_to_npy import (
    save_3d_data_to_npy,
)
from freemocap.core_processes.capture_volume_calibration.triangulate_3d_data import triangulate_3d_data
from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel

logger = logging.getLogger(__name__)


def run_reprojection_error_filtering(
    image_data_numCams_numFrames_numTrackedPts_XYZ: np.ndarray,
    raw_skel3d_frame_marker_xyz: np.ndarray,
    skeleton_reprojection_error_cam_fr_mar: np.ndarray,
    skeleton_reprojection_error_fr_mar: np.ndarray,
    anipose_calibration_object,
    processing_parameters: ProcessingParameterModel,
) -> np.ndarray:
    """
    Runs reprojection error filtering on 3d data, saves the filtered 3d data and reprojection error data, and creates and saves a debug plot.

    :param image_data_numCams_numFrames_numTrackedPts_XYZ: original 2d data
    :param raw_skel3d_frame_marker_xyz: original 3d data
    :param skeleton_reprojection_error_cam_fr_mar: original per camerareprojection error
    :param skeleton_reprojection_error_fr_mar: original per frame average reprojection error
    :param anipose_calibration_object: anipose calibration object
    :param processing_parameters: processing parameters

    :return: filtered 3d data
    """
    if hasattr(
        processing_parameters.tracking_model_info, "num_tracked_points_body"
    ):  # we don't want to reproject hand and face data
        num_tracked_points = processing_parameters.tracking_model_info.num_tracked_points_body
    else:
        num_tracked_points = processing_parameters.tracking_model_info.num_tracked_points

    (
        reprojection_filtered_skel3d_frame_marker_xyz,
        reprojection_filtered_skeleton_reprojection_error_fr_mar,
        reprojection_filtered_skeleton_reprojection_error_cam_fr_mar,
    ) = filter_by_reprojection_error(
        reprojection_error_camera_frame_marker=skeleton_reprojection_error_cam_fr_mar,
        reprojection_error_frame_marker=skeleton_reprojection_error_fr_mar,
        reprojection_error_confidence_threshold=processing_parameters.anipose_triangulate_3d_parameters_model.reprojection_error_confidence_cutoff,
        image_2d_data=image_data_numCams_numFrames_numTrackedPts_XYZ[:, :, :, :2],
        raw_skel3d_frame_marker_xyz=raw_skel3d_frame_marker_xyz,
        anipose_calibration_object=anipose_calibration_object,
        num_tracked_points=num_tracked_points,
        use_triangulate_ransac=processing_parameters.anipose_triangulate_3d_parameters_model.use_triangulate_ransac_method,
        minimum_cameras_to_reproject=processing_parameters.anipose_triangulate_3d_parameters_model.minimum_cameras_to_reproject,
    )
    save_3d_data_to_npy(
        data3d_numFrames_numTrackedPoints_XYZ=reprojection_filtered_skel3d_frame_marker_xyz,
        data3d_numFrames_numTrackedPoints_reprojectionError=reprojection_filtered_skeleton_reprojection_error_fr_mar,
        data3d_numCams_numFrames_numTrackedPoints_reprojectionError=reprojection_filtered_skeleton_reprojection_error_cam_fr_mar,
        path_to_folder_where_data_will_be_saved=processing_parameters.recording_info_model.raw_data_folder_path,
        processing_level="reprojection_filtered",
        file_prefix=processing_parameters.tracking_model_info.name,
    )
    plot_reprojection_error(
        raw_reprojection_error_frame_marker=skeleton_reprojection_error_fr_mar,
        filtered_reprojection_error_frame_marker=reprojection_filtered_skeleton_reprojection_error_fr_mar,
        reprojection_error_threshold=float(np.nanpercentile(
            skeleton_reprojection_error_cam_fr_mar,
            processing_parameters.anipose_triangulate_3d_parameters_model.reprojection_error_confidence_cutoff,
        )),
        output_folder_path=processing_parameters.recording_info_model.raw_data_folder_path,
    )
    return reprojection_filtered_skel3d_frame_marker_xyz


def filter_by_reprojection_error(
    reprojection_error_camera_frame_marker: np.ndarray,
    reprojection_error_frame_marker: np.ndarray,
    reprojection_error_confidence_threshold: float,
    image_2d_data: np.ndarray,
    raw_skel3d_frame_marker_xyz: np.ndarray,
    anipose_calibration_object,
    num_tracked_points: int,
    use_triangulate_ransac: bool = False,
    minimum_cameras_to_reproject: int = 3,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    total_cameras = image_2d_data.shape[0]
    num_cameras_to_remove = 1

    if total_cameras <= minimum_cameras_to_reproject:
        logger.warning(
            f"Not enough cameras to filter by reprojection error. There are {total_cameras} cameras, but minimum number of cameras is {minimum_cameras_to_reproject}. Returning unfiltered data."
        )
        return (
            raw_skel3d_frame_marker_xyz,
            reprojection_error_frame_marker,
            reprojection_error_camera_frame_marker,
        )

    body2d_camera_frame_marker_xy = image_2d_data[:, :, :num_tracked_points, :2]
    bodyReprojErr_camera_frame_marker = reprojection_error_camera_frame_marker[:, :, :num_tracked_points]

    reprojection_error_confidence_threshold = min(max(reprojection_error_confidence_threshold, 0), 100)

    reprojection_error_threshold = np.nanpercentile(
        np.nanmean(bodyReprojErr_camera_frame_marker, axis=0), reprojection_error_confidence_threshold, method="weibull"
    )  # TODO: try running this on reprojection_error_frame_marker with body points pulled out, rather than with cameras included
    logger.info(f"Using reprojection error threshold of {reprojection_error_threshold}")

    data_to_reproject_camera_frame_marker_xy, unique_frame_marker_list = _get_data_to_reproject(
        num_cameras_to_remove=num_cameras_to_remove,
        reprojection_error_threshold=reprojection_error_threshold,
        reprojError_cam_frame_marker=bodyReprojErr_camera_frame_marker,
        input_2d_data_camera_frame_marker_xy=body2d_camera_frame_marker_xy,
    )

    while len(unique_frame_marker_list) > 0 and total_cameras - num_cameras_to_remove >= minimum_cameras_to_reproject:
        logger.info("Retriangulating data")
        (
            retriangulated_data_frame_marker_xyz,
            new_reprojection_error_flat,
            new_reprojError_cam_frame_marker,
        ) = triangulate_3d_data(
            anipose_calibration_object=anipose_calibration_object,
            image_2d_data=data_to_reproject_camera_frame_marker_xy,
            use_triangulate_ransac=use_triangulate_ransac,
        )

        num_cameras_to_remove += 1

        data_to_reproject_camera_frame_marker_xy, unique_frame_marker_list = _get_data_to_reproject(
            num_cameras_to_remove=num_cameras_to_remove,
            reprojection_error_threshold=reprojection_error_threshold,
            reprojError_cam_frame_marker=new_reprojError_cam_frame_marker,
            input_2d_data_camera_frame_marker_xy=data_to_reproject_camera_frame_marker_xy,
        )

    # nan remaining data above threshold
    _nan_data_above_threshold(unique_frame_marker_list, retriangulated_data_frame_marker_xyz)

    # put retriangulated data back in place
    filtered_skel3d_frame_marker_xyz = raw_skel3d_frame_marker_xyz.copy()
    filtered_skel3d_frame_marker_xyz[:, :num_tracked_points, :] = retriangulated_data_frame_marker_xyz

    filtered_reprojection_error_frame_marker = reprojection_error_frame_marker.copy()
    filtered_reprojection_error_frame_marker[:, :num_tracked_points] = new_reprojection_error_flat

    filtered_reprojection_error_camera_frame_marker = reprojection_error_camera_frame_marker.copy()
    filtered_reprojection_error_camera_frame_marker[:, :, :num_tracked_points] = new_reprojError_cam_frame_marker

    return (
        filtered_skel3d_frame_marker_xyz,
        filtered_reprojection_error_frame_marker,
        filtered_reprojection_error_camera_frame_marker,
    )


def _nan_data_above_threshold(unique_frame_marker_list: list, retriangulated_data_frame_marker_xyz: np.ndarray) -> None:
    if len(unique_frame_marker_list) > 0:
        logger.info(
            f"Out of cameras to remove, setting {len(unique_frame_marker_list)} points with reprojection error above threshold to NaNs"
        )
        for frame_marker in unique_frame_marker_list:
            retriangulated_data_frame_marker_xyz[frame_marker[0], frame_marker[1], :] = np.nan


def _get_data_to_reproject(
    num_cameras_to_remove: int,
    reprojection_error_threshold: float,
    reprojError_cam_frame_marker: np.ndarray,
    input_2d_data_camera_frame_marker_xy: np.ndarray,
) -> tuple[np.ndarray, list]:
    indices_above_threshold = np.nonzero(reprojError_cam_frame_marker > reprojection_error_threshold)
    logger.debug(f"SHAPE OF INDICES ABOVE THRESHOLD: {indices_above_threshold[0].shape}")

    total_frame_marker_combos = (
        input_2d_data_camera_frame_marker_xy.shape[1] * input_2d_data_camera_frame_marker_xy.shape[2]
    )
    unique_frame_marker_list = _get_unique_frame_marker_list(indices_above_threshold=indices_above_threshold)
    logger.info(
        f"number of frame/marker combos with reprojection error above threshold: {len(unique_frame_marker_list)} ({len(unique_frame_marker_list) / total_frame_marker_combos * 100:.1f} percent of total)"
    )

    cameras_to_remove, frames_to_reproject, markers_to_reproject = _get_camera_frame_marker_lists_to_reproject(
        reprojError_cam_frame_marker=reprojError_cam_frame_marker,
        frame_marker_list=unique_frame_marker_list,
        num_cameras_to_remove=num_cameras_to_remove,
    )

    data_to_reproject_camera_frame_marker_xy = _set_unincluded_data_to_nans(
        input_2d_data=input_2d_data_camera_frame_marker_xy,
        frames_with_reprojection_error=frames_to_reproject,
        markers_with_reprojection_error=markers_to_reproject,
        cameras_to_remove=cameras_to_remove,
    )

    return (data_to_reproject_camera_frame_marker_xy, unique_frame_marker_list)


def _get_unique_frame_marker_list(
    indices_above_threshold: np.ndarray,
) -> list:
    return list(set(zip(indices_above_threshold[1], indices_above_threshold[2])))


def _get_camera_frame_marker_lists_to_reproject(
    reprojError_cam_frame_marker: np.ndarray,
    frame_marker_list: list,
    num_cameras_to_remove: int,
) -> Tuple[list, list, list]:
    """
    Generate the lists of cameras, frames, and markers to reproject based on the given input.
    Find the cameras with the worst reprojection errors for the given frames and markers.
    Args:
        reprojError_cam_frame_marker (np.ndarray): The array containing the reprojection errors for each camera, frame, and marker.
        frame_marker_list (list): The list of tuples containing the frame and marker indices.
        num_cameras_to_remove (int): The number of cameras to remove.
    Returns:
        Tuple[list, list, list]: A tuple containing the lists of cameras to remove, frames to reproject, and markers to reproject.
    """
    cameras_to_remove = []
    frames_to_reproject = []
    markers_to_reproject = []
    for frame, marker in frame_marker_list:
        frames_to_reproject.append(frame)
        markers_to_reproject.append(marker)
        max_indices = reprojError_cam_frame_marker[:, frame, marker].argsort()[::-1][:num_cameras_to_remove]
        cameras_to_remove.append(list(max_indices))
    return (cameras_to_remove, frames_to_reproject, markers_to_reproject)


def _set_unincluded_data_to_nans(
    input_2d_data: np.ndarray,
    frames_with_reprojection_error: list,
    markers_with_reprojection_error: list,
    cameras_to_remove: list[list[int]],
) -> np.ndarray:
    data_to_reproject = input_2d_data.copy()
    for list_of_cameras, frame, marker in zip(
        cameras_to_remove, frames_with_reprojection_error, markers_with_reprojection_error
    ):
        for camera in list_of_cameras:
            data_to_reproject[camera, frame, marker, :] = np.nan
    return data_to_reproject


def plot_reprojection_error(
    raw_reprojection_error_frame_marker: np.ndarray,
    filtered_reprojection_error_frame_marker: np.ndarray,
    reprojection_error_threshold: float,
    output_folder_path: Union[str, Path],
) -> None:
    title = "Mean Reprojection Error Per Frame"
    file_name = "debug_reprojection_error_filtering.png"
    output_filepath = Path(output_folder_path) / file_name
    raw_mean_reprojection_error_per_frame = np.nanmean(
        raw_reprojection_error_frame_marker,
        axis=1,
    )
    filtered_mean_reprojection_error_per_frame = np.nanmean(
        filtered_reprojection_error_frame_marker,
        axis=1,
    )
    plt.plot(raw_mean_reprojection_error_per_frame, color="blue", label="Data Before Filtering")
    plt.plot(filtered_mean_reprojection_error_per_frame, color="orange", alpha=0.9, label="Data After Filtering")
    plt.xlabel("Frame")
    plt.ylabel("Mean Reprojection Error Across Markers (mm)")
    plt.ylim(0, 2 * reprojection_error_threshold)
    plt.hlines(
        y=reprojection_error_threshold,
        xmin=0,
        xmax=len(raw_mean_reprojection_error_per_frame),
        color="red",
        label="Cutoff Threshold",
    )
    plt.title(title)
    plt.legend(loc="upper right")
    logger.info(f"Saving debug plots to: {output_filepath}")
    plt.savefig(output_filepath, dpi=300)
