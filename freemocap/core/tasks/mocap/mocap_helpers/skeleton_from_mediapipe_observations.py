
import logging
from pathlib import Path

import numpy as np
from skellyforge.data_models.trajectory_3d import Trajectory3d
from skellyforge.post_processing.filters.apply_filter import filter_trajectory
from skellyforge.post_processing.filters.filter_config import FilterConfig
from skellyforge.post_processing.interpolation.apply_interpolation import interpolate_trajectory
from skellyforge.post_processing.interpolation.interpolation_config import InterpolationConfig
from skellyforge.skellymodels.managers.human import Human


from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.tasks.triangulation.helpers.project_single_camera import project_2d_batch_to_3d
from freemocap.core.tasks.triangulation.triangulator import Triangulator

logger = logging.getLogger(__name__)


def _reorder_to_model_info_order(
    names: tuple[str, ...],
    model_info,
) -> np.ndarray:
    """Return a column-permutation that reorders observation columns into the
    order ``model_info`` expects (used by skellyforge's positional slicing).

    The new skellytracker pipeline merges stages in its own order (pose →
    face → right_hand → left_hand), while skellyforge's ``MediapipeModelInfo``
    YAML slices positionally in ``[body, right_hand, left_hand, face]`` order.
    Without reordering, the hands land on the face columns and vice-versa, so
    the 3D hand reconstruction reads the wrong 2D points.

    Columns are grouped by their stage-prefixed name (the new pipeline emits
    ``body.*`` for pose, ``body.face_*`` for face, and ``hands.right_hand_*`` /
    ``hands.left_hand_*`` for the hands child stage) and reassembled in the
    model_info aspect order, preserving within-group order.
    """
    groups: dict[str, list[int]] = {
        "body": [],
        "right_hand": [],
        "left_hand": [],
        "face": [],
    }
    for idx, n in enumerate(names):
        if n.startswith("body.face"):
            groups["face"].append(idx)
        elif n.startswith("hands.right_hand"):
            groups["right_hand"].append(idx)
        elif n.startswith("hands.left_hand"):
            groups["left_hand"].append(idx)
        else:
            groups["body"].append(idx)

    perm: list[int] = []
    for aspect_name in model_info.order:
        perm.extend(groups[aspect_name])
    return np.asarray(perm, dtype=np.intp)


def skeleton_from_mediapipe_observation_recorders(
    detector:str,
    observation_recorders: dict[CameraIdString, ObservationBuffer],
    path_to_calibration_toml: Path | str | None,
    path_to_output_data_folder: Path | str,
    triangulation_config: TriangulationConfig | None = None,
    interp_config: InterpolationConfig | None = None,
    filter_config: FilterConfig | None = None,
) -> Human:
    """Triangulate skeleton 2D observations into a 3D skeleton.

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

    # Extract 2D data from observation buffers
    data2d_by_camera: dict[CameraIdString, np.ndarray] = {}
    # Determine the model-info column order up front (mediapipe only): the new
    # skellytracker pipeline merges stages in [pose, face, right_hand, left_hand]
    # order, but skellyforge's MediapipeModelInfo slices positionally in
    # [body, right_hand, left_hand, face] order. Without a reorder, the hands
    # would be read from the face columns and vice-versa.
    reorder_perm: np.ndarray | None = None
    if detector == "mediapipe":
        from skellyforge.skellymodels.models.tracking_model_info import MediapipeModelInfo
        model_info = MediapipeModelInfo()
        for buf in observation_recorders.values():
            if buf.observations:
                merged_names = buf.observations[0].to_keypoints().names
                reorder_perm = _reorder_to_model_info_order(merged_names, model_info)
                break

    for camera_id, buf in observation_recorders.items():
        data2d_fr_id_xyc = buf.to_keypoints_array().copy()
        if reorder_perm is not None:
            data2d_fr_id_xyc = data2d_fr_id_xyc[:, reorder_perm, :]
        logger.info(f"Processing camera ID: {camera_id} with 2D data shape: {data2d_fr_id_xyc.shape}")
        data2d_by_camera[camera_id] = data2d_fr_id_xyc[..., :2]

    camera_ids = list(data2d_by_camera.keys())

    if len(camera_ids) == 1:
        data2d = data2d_by_camera[camera_ids[0]]
        result = project_2d_batch_to_3d(data2d=data2d)
    else:
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

    logger.info(f"Filtering trajectory with config: {filter_config.model_dump_json(indent=2)}")
    filtered_trajectory_3d: Trajectory3d = filter_trajectory(
        trajectory=interpolated_trajectory_3d,
        config=filter_config,
    )

    match detector:
        case "mediapipe":
            from skellyforge.skellymodels.models.tracking_model_info import MediapipeModelInfo
            model_info = MediapipeModelInfo()
        case "rtmpose":
            from skellyforge.skellymodels.models.tracking_model_info import RTMPoseModelInfo
            model_info = RTMPoseModelInfo()
        case _:
            raise ValueError(f"Unknown detector: {detector}")

    skeleton: Human = Human.from_tracked_points_numpy_array(
        name="human",
        model_info=model_info,
        tracked_points_numpy_array=filtered_trajectory_3d.triangulated_data,
    )

    print("DETECTOR: ", detector)
    print("MODEL INFO: ", model_info)
    print(f"SKELETON: {skeleton}")

    if len(camera_ids) > 1 and not calibration.groundplane_aligned:
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
