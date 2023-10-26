import logging
from typing import Tuple, List, Union

import bpy
import numpy as np

from ajc_freemocap_blender_addon.data_models.mediapipe_names.mediapipe_heirarchy import MEDIAPIPE_HIERARCHY

logger = logging.getLogger(__name__)


def translate_empty_and_its_children(empty_name: str,
                                     frame_index: int,
                                     delta: Union[List[float], Tuple[float, float, float], np.ndarray]):
    if isinstance(delta, np.ndarray) or isinstance(delta, tuple):
        delta = list(delta)

    if not len(delta) == 3:
        raise ValueError(f"Delta must be a list of length 3, not {len(delta)}")

    try:
        # Translate the empty in the animation location curve

        bpy.data.objects[empty_name].animation_data.action.fcurves[0].keyframe_points[frame_index].co[1] += delta[0]

        bpy.data.objects[empty_name].animation_data.action.fcurves[1].keyframe_points[frame_index].co[1] += delta[1]

        bpy.data.objects[empty_name].animation_data.action.fcurves[2].keyframe_points[frame_index].co[1] = delta[2]
    except:
        # Empty does not exist or does not have animation data
        # print('Empty ' + empty + ' does not have animation data on frame ' + str(frame_index))
        pass

    # If empty has children then call this function for every child
    if empty_name in MEDIAPIPE_HIERARCHY.keys():
        logger.debug(
            f"Translating children of empty {empty_name}: {MEDIAPIPE_HIERARCHY[empty_name]['children']}")
        for child in MEDIAPIPE_HIERARCHY[empty_name]['children']:
            translate_empty_and_its_children(empty_name=child,
                                             frame_index=frame_index,
                                             delta=delta)
