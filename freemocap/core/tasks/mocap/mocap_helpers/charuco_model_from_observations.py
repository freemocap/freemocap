"""Build a charuco board 3D model from tracked observations.

Shared post-calibration step used by both anipose and pyceres paths.
Triangulates 2D charuco detections into 3D using the calibrated cameras,
then interpolates, filters, and saves the result.
"""

import logging
from pathlib import Path

from skellyforge.post_processing.filters.apply_filter import filter_trajectory
from skellyforge.post_processing.filters.filter_config import FilterConfig
from skellyforge.post_processing.interpolation.apply_interpolation import interpolate_trajectory
from skellyforge.post_processing.interpolation.interpolation_config import InterpolationConfig
from skellyforge.skellymodels.managers.board import Board
from skellyforge.skellymodels.models.tracking_model_info import CharucoBoard5x3ModelInfo, CharucoBoard7x5ModelInfo
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.mocap.mocap_helpers.triangulate_trajectory_array import triangulate_dict
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.triangulation.triangulator import Triangulator


from skellyforge.data_models.trajectory_3d import Trajectory3d  # noqa: TC002
import numpy as np  # noqa: TC002

logger = logging.getLogger(__name__)


def charuco_model_from_observations(
    *,
    observation_buffers: dict[CameraIdString, ObservationBuffer],
    board_def: CharucoBoardDefinition,
    output_data_folder: Path | str,
    calibration_toml_path: Path | str | None,
    triangulator: Triangulator | None = None,
    triangulation_config: TriangulationConfig | None = None,
    interp_config: InterpolationConfig | None = None,
    filter_config: FilterConfig | None = None,
) -> Board:
    """Triangulate, interpolate, filter charuco observations and save the 3D board model."""
    if triangulation_config is None:
        triangulation_config = TriangulationConfig()
    if interp_config is None:
        interp_config = InterpolationConfig()
    if filter_config is None:
        filter_config = FilterConfig()

    if triangulator is not None and calibration_toml_path is not None:
        raise ValueError("Provide either triangulator or calibration_toml_path, not both.")
    if triangulator is None and calibration_toml_path is None:
        raise ValueError("Must provide either triangulator or calibration_toml_path.")
    if calibration_toml_path is not None:
        calibration = CalibrationResult.load_anipose_toml(Path(calibration_toml_path))
        triangulator = Triangulator.from_calibration_result(calibration=calibration)

    Path(output_data_folder).mkdir(parents=True, exist_ok=True)

    data2d_by_camera: dict[CameraIdString, np.ndarray] = {}
    if len(observation_buffers) == 0:
        raise ValueError("No observation buffers provided to process.")

    for camera_id, buf in observation_buffers.items():
        for obs in buf.observations:
            if "charuco" not in obs.stages:
                raise TypeError(f"Buffer for camera ID {camera_id} contains non-charuco observations.")
        data2d_fr_id_xyc = buf.to_stage_array("charuco", n_points=board_def.n_corners).copy()
        logger.info(f"Processing camera ID: {camera_id} with 2D data shape: {data2d_fr_id_xyc.shape}")
        data2d_by_camera[camera_id] = data2d_fr_id_xyc[..., :2]

    raw_trajectory_3d: Trajectory3d = triangulate_dict(
        data2d_fr_mar_xy_by_camera=data2d_by_camera,
        triangulator=triangulator,
        config=triangulation_config,
    )

    interpolated_trajectory_3d: Trajectory3d = interpolate_trajectory(
        trajectory=raw_trajectory_3d,
        config=interp_config,
    )

    filtered_trajectory_3d: Trajectory3d = filter_trajectory(
        trajectory=interpolated_trajectory_3d,
        config=filter_config,
    )

    if board_def.squares_x == 5 and board_def.squares_y == 3:
        model_info = CharucoBoard5x3ModelInfo()
        name = "charuco_board_5x3"
    elif board_def.squares_x == 7 and board_def.squares_y == 5:
        model_info = CharucoBoard7x5ModelInfo()
        name = "charuco_board_7x5"
    else:
        raise ValueError(f"Unsupported board definition: x: {board_def.squares_x}, y: {board_def.squares_y}")

    charuco_model = Board.from_tracked_points_numpy_array(
        name=name,
        model_info=model_info,
        tracked_points_numpy_array=filtered_trajectory_3d.triangulated_data,
    )

    charuco_model.save_out_numpy_data(output_data_folder)
    charuco_model.save_out_csv_data(output_data_folder)
    # charuco_model.save_out_all_data_csv(output_data_folder) #saves out the exact same data as the above two lines, so don't need it
    # charuco_model.save_out_all_xyz_numpy_data(output_data_folder) #saves out the exact same data as the above two lines, so don't need it
    charuco_model.save_out_all_data_parquet(output_data_folder)

    return charuco_model
