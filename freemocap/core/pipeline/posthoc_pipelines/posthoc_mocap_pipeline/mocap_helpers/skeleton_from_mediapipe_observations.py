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

from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.freemocap_anipose import \
    AniposeCameraGroup
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.mocap_helpers.triangulate_trajectory_array import \
    TriangulationConfig, triangulate_dict
from freemocap.core.types.type_overloads import VideoIdString

logger = logging.getLogger(__name__)

def skeleton_from_mediapipe_observation_recorders(observation_recorders:dict[VideoIdString, BaseRecorder],
                                                  path_to_calibration_toml: Path | str,
                                                  path_to_output_data_folder: Path | str,
                                                  triangulation_config: TriangulationConfig|None = None,
                                                  interp_config: InterpolationConfig|None = None,
                                                  filter_config: FilterConfig|None = None,
                                                  ) -> Human:

    if triangulation_config is None:
        triangulation_config = TriangulationConfig()
    if interp_config is None:
        interp_config = InterpolationConfig()
    if filter_config is None:
        filter_config = FilterConfig()

    Path(path_to_output_data_folder).mkdir(parents=True,
                                           exist_ok=True)

    data2d_by_video: dict[VideoIdString, np.ndarray] = {}
    if len(observation_recorders) == 0:
        raise ValueError("No observation recorders provided to process.")

    for video_id, recorder in observation_recorders.items():
        data2d_fr_id_xyc = recorder.to_array.copy()
        logger.info(f"Processing video ID: {video_id} with 2D data shape: {data2d_fr_id_xyc.shape}")
        data2d_by_video[video_id] = data2d_fr_id_xyc[..., :2]

    camera_group=AniposeCameraGroup.load(str(path_to_calibration_toml))

    raw_trajectory_3d: Trajectory3d = triangulate_dict(
        data2d_fr_mar_xyz_by_camera=data2d_by_video,
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

    skeleton: Human = Human.from_tracked_points_numpy_array(
        # name/model info are hardcoded - but ideally we'll make a some sort of config that we'll pull from to choose these
        name="human",
        model_info=MediapipeModelInfo(),
        tracked_points_numpy_array=filtered_trajectory_3d.triangulated_data,
    )

    try:
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
