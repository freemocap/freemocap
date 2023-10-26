import logging
from typing import List, Union, Dict

import bpy
import numpy as np

logger = logging.getLogger(__name__)


def create_empties(trajectory_frame_marker_xyz: np.ndarray,
                   names_list: Union[List[str], str],
                   empty_scale: float,
                   empty_type: str,
                   parent_object: bpy.types.Object,
                   ) -> Dict[str, bpy.types.Object]:
    if isinstance(names_list, str):
        names_list = [names_list] * trajectory_frame_marker_xyz.shape[1]
    empties = {}
    number_of_trajectories = trajectory_frame_marker_xyz.shape[1]
    for marker_number in range(number_of_trajectories):
        trajectory_name = names_list[marker_number]
        trajectory_fr_xyz = trajectory_frame_marker_xyz[:, marker_number, :]
        empties[trajectory_name] = create_keyframed_empty_from_3d_trajectory_data(
            trajectory_fr_xyz=trajectory_fr_xyz,
            trajectory_name=trajectory_name,
            parent_object=parent_object,
            empty_scale=empty_scale,
            empty_type=empty_type,
        )
        logger.trace(f"Created empty {trajectory_name}")

    return empties


def create_keyframed_empty_from_3d_trajectory_data(
        trajectory_fr_xyz: np.ndarray,
        trajectory_name: str,
        parent_object: bpy.types.Object,
        empty_scale: float = 0.1,
        empty_type: str = "PLAIN_AXES",
) -> bpy.types.Object:
    """
    Create a key framed empty from 3d trajectory data
    """
    logger.info(f"Creating keyframed empty from: {trajectory_name}...")
    bpy.ops.object.empty_add(type=empty_type)
    empty_object = bpy.context.editable_objects[-1]
    empty_object.name = trajectory_name

    empty_object.scale = [empty_scale] * 3

    empty_object.parent = parent_object

    for frame_number in range(trajectory_fr_xyz.shape[0]):
        empty_object.location = [
            trajectory_fr_xyz[frame_number, 0],
            trajectory_fr_xyz[frame_number, 1],
            trajectory_fr_xyz[frame_number, 2],
        ]

        empty_object.keyframe_insert(data_path="location", frame=frame_number)

    return empty_object
