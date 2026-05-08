
import logging
from pathlib import Path

import numpy as np
from skellyforge.data_models.trajectory_3d import Trajectory3d
from skellyforge.post_processing.filters.apply_filter import filter_trajectory
from skellyforge.post_processing.filters.filter_config import FilterConfig
from skellyforge.post_processing.interpolation.apply_interpolation import interpolate_trajectory
from skellyforge.post_processing.interpolation.interpolation_config import InterpolationConfig
from skellyforge.skellymodels.managers.human import Human
from skellyforge.skellymodels.models.tracking_model_info import MediapipeModelInfo
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder

from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.triangulation.triangulator import Triangulator

logger = logging.getLogger(__name__)


def skeleton_from_mediapipe_observation_recorders(
    observation_recorders: dict[CameraIdString, BaseRecorder],
    path_to_calibration_toml: Path | str,
    path_to_output_data_folder: Path | str,
    triangulation_config: TriangulationConfig | None = None,
    interp_config: InterpolationConfig | None = None,
    filter_config: FilterConfig | None = None,
) -> Human:
    """Triangulate mediapipe 2D observations into a 3D skeleton.

    Camera matching: observation_recorders keys (CameraIdString)
    are matched to calibration camera names. Each key must have an exact match
    in the calibration file's camera names.
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

    # Extract 2D data from observation recorders
    data2d_by_camera: dict[CameraIdString, np.ndarray] = {}
    for camera_id, recorder in observation_recorders.items():
        data2d_fr_id_xyc = recorder.to_array.copy()
        logger.info(f"Processing camera ID: {camera_id} with 2D data shape: {data2d_fr_id_xyc.shape}")
        data2d_by_camera[camera_id] = data2d_fr_id_xyc[..., :2]

    # Load calibration and build triangulator matched to our camera IDs
    calibration = CalibrationResult.load_anipose_toml(Path(path_to_calibration_toml))
    camera_ids = list(data2d_by_camera.keys())

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

    n_frames = raw_3d.shape[0]
    raw_trajectory_3d = Trajectory3d(
        start_frame=0,
        end_frame=n_frames,
        triangulated_data=raw_3d,
        reprojection_error=np.nanmean(result.reprojection_error, axis=0),
        reprojection_error_by_camera=result.reprojection_error,
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
        model_info=MediapipeModelInfo(),
        tracked_points_numpy_array=filtered_trajectory_3d.triangulated_data,
    )


    if not calibration.groundplane_aligned:
        try:
            logger.debug("Groundplane undefined in calibration - aligning to skeleton feet")
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
