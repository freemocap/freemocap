
import logging
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from skellyforge.data_models.trajectory_3d import Trajectory3d
from skellyforge.post_processing.filters.apply_filter import filter_trajectory
from skellyforge.post_processing.filters.filter_config import FilterConfig
from skellyforge.post_processing.interpolation.apply_interpolation import interpolate_trajectory
from skellyforge.post_processing.interpolation.interpolation_config import InterpolationConfig
from skellyforge.skellymodels.managers.human import Human
from skellyforge.skellymodels.models.tracking_model_info import MediapipeModelInfo, ModelInfo, RTMPoseModelInfo
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder
from skellytracker.trackers.mediapipe_tracker import MediapipeObservation
from skellytracker.trackers.rtmpose_tracker.rtmpose_observation import RTMPoseObservation

from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.triangulation.triangulator import Triangulator

logger = logging.getLogger(__name__)

# Rough assumed height of a tracked person, used to scale single-camera pixel
# coordinates into a human-sized range when no depth information is available.
_ASSUMED_PERSON_HEIGHT_METERS = 1.7


def _model_info_for_recorders(observation_recorders: dict[CameraIdString, BaseRecorder]) -> ModelInfo:
    """Pick the skellyforge ModelInfo matching the tracker type used to record observations."""
    first_observation = next(iter(observation_recorders.values())).observations[0]
    if isinstance(first_observation, RTMPoseObservation):
        return RTMPoseModelInfo()
    if isinstance(first_observation, MediapipeObservation):
        return MediapipeModelInfo()
    raise TypeError(f"Unsupported observation type for skeleton building: {type(first_observation).__name__}")


def _flat_3d_from_pixels(
    data2d: NDArray[np.float64],
    image_size: tuple[int, int] | None,
) -> NDArray[np.float64]:
    """Build a flat (Z=0) 3D trajectory from a single camera's 2D pixel observations.

    No depth information is available from a single camera, so every point is
    placed on the Z=0 plane. Each frame is centered on the centroid of its valid
    points and pixel units are scaled to a roughly human-sized range so the
    output is usable downstream (filtering, Blender export, etc.) without huge
    pixel-scale coordinates.

    Args:
        data2d: (n_frames, n_points, 2) pixel coordinates.
        image_size: (height, width) of the source images, if known.

    Returns:
        (n_frames, n_points, 3) array with Z == 0 everywhere.
    """
    x = data2d[..., 0]
    y = data2d[..., 1]

    if image_size is not None and image_size[0] > 0:
        height_px = float(image_size[0])
    else:
        height_px = float(np.nanmax(y) - np.nanmin(y))
        if not np.isfinite(height_px) or height_px == 0:
            height_px = 1.0

    scale = _ASSUMED_PERSON_HEIGHT_METERS / height_px

    centroid_x = np.nanmean(x, axis=1, keepdims=True)
    centroid_y = np.nanmean(y, axis=1, keepdims=True)

    x_3d = (x - centroid_x) * scale
    # Flip Y so that "up" in the image (smaller pixel Y) is positive, matching
    # a typical world-coordinate up axis.
    y_3d = (centroid_y - y) * scale
    z_3d = np.zeros_like(x_3d)

    return np.stack([x_3d, y_3d, z_3d], axis=-1)


def skeleton_from_mediapipe_observation_recorders(
    observation_recorders: dict[CameraIdString, BaseRecorder],
    path_to_calibration_toml: Path | str | None,
    path_to_output_data_folder: Path | str,
    triangulation_config: TriangulationConfig | None = None,
    interp_config: InterpolationConfig | None = None,
    filter_config: FilterConfig | None = None,
) -> Human:
    """Build a 3D skeleton from per-camera 2D observations.

    With 2+ cameras, observations are triangulated using the provided calibration.
    Camera matching: observation_recorders keys (CameraIdString) are matched to
    calibration camera names. Each key must have an exact match in the
    calibration file's camera names.

    With a single camera, no calibration is required: each frame is flattened
    onto the Z=0 plane directly from its 2D pixel observations.
    """
    if triangulation_config is None:
        triangulation_config = TriangulationConfig()
    if interp_config is None:
        interp_config = InterpolationConfig()
    if filter_config is None:
        filter_config = FilterConfig()

    Path(path_to_output_data_folder).mkdir(parents=True, exist_ok=True)

    if len(observation_recorders) == 0:
        raise ValueError("No observation recorders provided to process.")

    model_info = _model_info_for_recorders(observation_recorders)

    # Extract 2D data from observation recorders
    data2d_by_camera: dict[CameraIdString, np.ndarray] = {}
    for camera_id, recorder in observation_recorders.items():
        data2d_fr_id_xyc = recorder.to_array.copy()
        logger.info(f"Processing camera ID: {camera_id} with 2D data shape: {data2d_fr_id_xyc.shape}")
        data2d_by_camera[camera_id] = data2d_fr_id_xyc[..., :2]

    camera_ids = list(data2d_by_camera.keys())

    if len(camera_ids) == 1:
        logger.info("Single camera provided - skipping triangulation and building a flat (Z=0) skeleton")
        only_camera_id = camera_ids[0]
        recorder = observation_recorders[only_camera_id]
        image_size = getattr(recorder.observations[0], "image_size", None)

        raw_3d = _flat_3d_from_pixels(data2d=data2d_by_camera[only_camera_id], image_size=image_size)

        n_frames, n_points = raw_3d.shape[0], raw_3d.shape[1]
        reprojection_error = np.zeros((n_frames, n_points), dtype=np.float64)
        reprojection_error_by_camera = np.zeros((1, n_frames, n_points), dtype=np.float64)
        groundplane_aligned = False
    else:
        # Load calibration and build triangulator matched to our camera IDs
        if path_to_calibration_toml is None:
            raise ValueError("path_to_calibration_toml is required when triangulating from 2+ cameras")
        calibration = CalibrationResult.load_anipose_toml(Path(path_to_calibration_toml))

        triangulator = Triangulator.from_calibration_for_cameras(
            calibration=calibration,
            camera_ids=camera_ids,
        )

        result = triangulator.triangulate(
            data2d=data2d_by_camera,
            config=triangulation_config,
        )
        raw_3d = result.points_3d

        # Persist per-camera weights as a sibling NPY (only useful when outlier rejection is on,
        # but always written so downstream can read consistently).
        #TODO - Make this less dumb and sloppy
        np.save(
            Path(path_to_output_data_folder) / "per_camera_weights.npy",
            result.per_camera_weights,
        )

        reprojection_error = np.nanmean(result.reprojection_error, axis=0)
        reprojection_error_by_camera = result.reprojection_error
        groundplane_aligned = calibration.groundplane_aligned

    n_frames = raw_3d.shape[0]
    raw_trajectory_3d = Trajectory3d(
        start_frame=0,
        end_frame=n_frames,
        triangulated_data=raw_3d,
        reprojection_error=reprojection_error,
        reprojection_error_by_camera=reprojection_error_by_camera,
    )

    interpolated_trajectory_3d: Trajectory3d = interpolate_trajectory(
        trajectory=raw_trajectory_3d,
        config=interp_config,
    )

    filtered_trajectory_3d: Trajectory3d = filter_trajectory(
        trajectory=interpolated_trajectory_3d,
        config=filter_config,
    )

    skeleton: Human = Human.from_tracked_points_numpy_array(
        name="human",
        model_info=model_info,
        tracked_points_numpy_array=filtered_trajectory_3d.triangulated_data,
    )


    if not groundplane_aligned:
        try:
            logger.debug("Groundplane undefined - aligning to skeleton feet")
            skeleton.put_skeleton_on_ground()
        except Exception as e:
            logger.warning(f"Could not put skeleton on ground: {e}")

    try:
        skeleton.fix_hands_to_wrist()
    except Exception as e:
        logger.warning(f"Could not fix hands to wrist: {e}")

    skeleton.calculate()

    skeleton.save_out_numpy_data(path_to_output_data_folder)
    skeleton.save_out_csv_data(path_to_output_data_folder)
    skeleton.save_out_all_data_csv(path_to_output_data_folder)
    skeleton.save_out_all_data_parquet(path_to_output_data_folder)
    skeleton.save_out_all_xyz_numpy_data(path_to_output_data_folder)

    return skeleton
