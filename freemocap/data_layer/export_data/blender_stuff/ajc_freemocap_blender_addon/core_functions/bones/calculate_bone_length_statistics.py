import logging
import math
import statistics
from typing import Dict, Any

import numpy as np

logger = logging.getLogger(__name__)


def calculate_bone_length_statistics(trajectories: Dict[str, np.ndarray],
                                     bones: Dict[str, Dict[str, Any]]):
    logger.info('Calculating bone length statistics...')

    # Reset the lengths list for every virtual bone
    for bone in bones:
        bones[bone]['lengths'] = []

    bones['hand.R']['tail'] = 'right_hand_middle'
    bones['hand.L']['tail'] = 'left_hand_middle'

    # Iterate through the empty_positions dictionary and calculate the distance between the head and tail and append it to the lengths list
    logger.trace(f'Calculating bone length statistics...')
    for frame_number in range(0, trajectories['hips_center'].shape[0]):
        # Iterate through each bone
        for bone_name, bone_dict in bones.items():
            # Calculate the length of the bone for this frame
            head_name = bone_dict['head']
            tail_name = bone_dict['tail']

            head_pos = list(trajectories[head_name][frame_number, :])
            tail_pos = list(trajectories[tail_name][frame_number, :])

            bone_dict['lengths'].append(math.dist(head_pos, tail_pos))

    logger.success(f'Bone lengths calculated successfully!\n\n bones: \n\n {bones.keys()}')
    # Update the length median and stdev values for each bone
    for name, bone in bones.items():
        logger.trace(f'Calculating median and stdev for bone: {name}...')
        # Exclude posible length NaN (produced by an empty with NaN values as position) values from the median and standard deviation
        bone['median'] = statistics.median(
            [length for length in bone['lengths'] if not math.isnan(length)])
        # virtual_bone['median'] = statistics.median(virtual_bone['lengths'])
        bone['stdev'] = statistics.stdev(
            [length for length in bone['lengths'] if not math.isnan(length)])
        # virtual_bone['stdev'] = statistics.stdev(virtual_bone['lengths'])

    logger.success(f'Bone length statistics calculated successfully!\n\n bones: \n\n {bones.keys()}')

    return bones
