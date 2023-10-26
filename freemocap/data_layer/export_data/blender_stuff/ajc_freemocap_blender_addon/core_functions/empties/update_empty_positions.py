import logging
import math as m
from typing import Dict, Any

import bpy

logger = logging.getLogger(__name__)

EMPTY_VELOCITIES = {}
EMPTY_POSITIONS = {}


def get_empty_positions(empties: Dict[str, bpy.types.Object], ) -> dict[str, dict[str, list[Any]]]:
    logger.info('Updating Empty Positions Dictionary...')

    # Get the scene context
    scene = bpy.context.scene
    current_frame = scene.frame_current
    # Change to Object Mode
    bpy.ops.object.mode_set(mode="OBJECT")

    # # Reset the empty positions dictionary with empty arrays for each empty
    # for object in bpy.data.objects:
    #     if object.type == 'EMPTY' and object.name != 'freemocap_origin_axes' and object.name != 'world_origin' and object.name != '_full_body_center_of_mass':
    #         EMPTY_POSITIONS[object.name] = {'x': [], 'y': [], 'z': []}

    empty_positions = {}
    for empty_name in empties.keys():
        empty_positions[empty_name] = {'x': [], 'y': [], 'z': []}

    # Iterate through each scene frame and save the coordinates of each empty in the dictionary. Frame is displaced by -1 to match animation curves.
    for frame in range(scene.frame_start, scene.frame_end):
        # Set scene frame
        scene.frame_set(frame)
        # Iterate through each object
        for name, component in empties.items():
            for name, empty in component.items():
                empty_positions[name]['x'].append(empty.location[0])
                empty_positions[name]['y'].append(empty.location[1])
                empty_positions[name]['z'].append(empty.location[2])

    # Reset the scene frame to where it was before
    scene.frame_set(current_frame)

    logger.info('Empty Positions Dictionary update completed.')
    return empty_positions


def update_empty_velocities(recording_fps,
                            ):
    logger.info('Updating Empty Speeds Dictionary...')

    # Get the scene context
    scene = bpy.context.scene

    # Change to Object Mode
    bpy.ops.object.mode_set(mode="OBJECT")

    # Reset the empty speeds dictionary with an array with one element of value zero for each empty marker
    for object in bpy.data.objects:
        if object.type == 'EMPTY' and object.name != 'freemocap_origin_axes' and object.name != 'world_origin' and object.name != '_full_body_center_of_mass':
            EMPTY_VELOCITIES[object.name] = {'speed': [0]}

    # Iterate through each scene frame starting from frame start + 1 and save the speed of each empty in the dictionary
    for frame in range(scene.frame_start + 1, scene.frame_end + 1):
        # Set scene frame
        scene.frame_set(frame)
        # Iterate through each object
        for object in bpy.data.objects:
            if object.type == 'EMPTY' and object.name != 'freemocap_origin_axes' and object.name != 'world_origin' and object.name != '_full_body_center_of_mass':
                # Save the speed of the empty based on the recording fps and the distance to the position of the empty in the previous frame
                # logger.info('length:' + str(len(empty_positions[object.name]['x'])))
                # logger.info('frame:'+str(frame))
                current_frame_position = \
                    (EMPTY_POSITIONS[object.name]['x'][frame - 1], EMPTY_POSITIONS[object.name]['y'][frame - 1],
                     EMPTY_POSITIONS[object.name]['z'][frame - 1])
                previous_frame_position = (
                    EMPTY_POSITIONS[object.name]['x'][frame - 2], EMPTY_POSITIONS[object.name]['y'][frame - 2],
                    EMPTY_POSITIONS[object.name]['z'][frame - 2])
                seconds_per_frame = 1 / recording_fps
                EMPTY_VELOCITIES[object.name]['speed'].append(
                    m.dist(current_frame_position, previous_frame_position) / seconds_per_frame)

    # Reset the scene frame to the start
    # scene.frame_set(scene.frame_start)

    logger.info('Empty Speeds Dictionary update completed.')
