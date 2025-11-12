import logging
from pathlib import Path

import numpy as np
from skellyforge.post_processing.filters.apply_filter import filter_trajectory
from skellyforge.post_processing.filters.filter_config import FilterConfig
from skellyforge.post_processing.interpolation.apply_interpolation import interpolate_trajectory
from skellyforge.post_processing.interpolation.interpolation_config import InterpolationConfig
from skellyforge.skellymodels.models.tracking_model_info import MediapipeModelInfo, CharucoBoard5x3ModelInfo
from skellyforge.skellymodels.managers.board import Board
from skellyforge.data_models.trajectory_3d import Trajectory3d

from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.freemocap_anipose import \
    AniposeCameraGroup
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.mocap_helpers.triangulate_trajectory_array import \
    TriangulationConfig, triangulate_dict
from freemocap.core.types.type_overloads import VideoIdString

logger = logging.getLogger(__name__)


def charuco_model_from_observations(observation_recorders: dict[VideoIdString, BaseRecorder],
                                    calibration_toml_path: Path | str,
                                    output_data_folder: Path | str,
                                    triangulation_config: TriangulationConfig | None = None,
                                    interp_config: InterpolationConfig | None = None,
                                    filter_config: FilterConfig | None = None,
                                    ) -> Board:
    if triangulation_config is None:
        triangulation_config = TriangulationConfig()
    if interp_config is None:
        interp_config = InterpolationConfig()
    if filter_config is None:
        filter_config = FilterConfig()

    Path(output_data_folder).mkdir(parents=True,
                                   exist_ok=True)

    data2d_by_video: dict[VideoIdString, np.ndarray] = {}
    if len(observation_recorders) == 0:
        raise ValueError("No observation recorders provided to process.")

    for video_id, recorder in observation_recorders.items():
        if not all([isinstance(observation, CharucoObservation) for observation in recorder.observations]):
            raise TypeError(f"Recorder for video ID {video_id} contains non-Charuco observations.")
        data2d_fr_id_xyc = recorder.to_array.copy()
        logger.info(f"Processing video ID: {video_id} with 2D data shape: {data2d_fr_id_xyc.shape}")
        data2d_by_video[video_id] = data2d_fr_id_xyc[..., :2]

    camera_group= AniposeCameraGroup.load(str(calibration_toml_path))

    raw_trajectory_3d: Trajectory3d = triangulate_dict(
        data_dict=data2d_by_video,
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

    charuco_model = Board.from_tracked_points_numpy_array(
        # name/model info are hardcoded - but ideally we'll make a some sort of config that we'll pull from to choose these
        name="charuco_board_5x3",
        model_info=CharucoBoard5x3ModelInfo(),
        tracked_points_numpy_array=filtered_trajectory_3d.triangulated_data,
    )


    charuco_model.save_out_numpy_data(output_data_folder)
    charuco_model.save_out_csv_data(output_data_folder)
    charuco_model.save_out_all_data_csv(output_data_folder)
    charuco_model.save_out_all_data_parquet(output_data_folder)
    charuco_model.save_out_all_xyz_numpy_data(output_data_folder)

    return charuco_model
