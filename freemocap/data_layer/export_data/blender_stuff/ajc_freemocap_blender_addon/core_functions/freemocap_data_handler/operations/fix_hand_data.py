import logging
from typing import List

import numpy as np
from numpy import dot

from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.handler import \
    FreemocapDataHandler

logger = logging.getLogger(__name__)


def fix_hand_data(handler: FreemocapDataHandler):
    """
    fix hand data by...

    On each frame:
    1. translate hand data so "right/left_hand_wrist" trajectory (hand data) is on top of the "right/left_wrist" trajectory (body data)
    2. rotate hand data so "right/left_index_finger_mcp" trajectory (hand data) is on top of the "right/left_index" trajectory (hand data)
    3. rotate hand data so "right/left_pinky_mcp" trajectory (hand data) is on top of the "right/left_pinky" trajectory (hand data)
    """
    logger.info(
        "Fixing hand data (i.e. aligning the `left/right_hand...` data with the body's more impoverished hand data)")

    hand_data_frame_name_xyz = {"right": handler.right_hand_frame_name_xyz,
                                "left": handler.left_hand_frame_name_xyz}

    try:
        for side, hand_data_frame_name_xyz in hand_data_frame_name_xyz.items():
            # 1. translate hand data so "right/left_hand_wrist" trajectory (hand data) is on top of the "right/left_wrist" trajectory (body data)
            hand_wrist_frame_xyz = handler.trajectories[f"{side}_hand_wrist"]
            body_wrist_frame_xyz = handler.trajectories[f"{side}_wrist"]
            position_delta = body_wrist_frame_xyz - hand_wrist_frame_xyz
            handler.translate(translation=position_delta.tolist(),
                              component_name=f"{side}_hand")

            # TODO - consider implementing or removing this - its not clear if this is a good idea,
            #  it's possible that the body/hand data is less accurate about rotation than hand/hand data? like, I think
            #  it underestimates wrist rotation amplitudes?
            #
            # hand_index_finger_mcp_frame_xyz = handler.trajectories[f"{side}_hand_index_finger_mcp"]
            # body_hand_index_frame_xyz = handler.trajectories[f"{side}_index"]
            # hand_index_finger_mcp_vector = hand_index_finger_mcp_frame_xyz - hand_wrist_frame_xyz
            # body_index_finger_vector = body_hand_index_frame_xyz - hand_wrist_frame_xyz
            #
            # # Calculate rotation matrix to align index finger
            # index_finger_rotation_matricies = calculate_rotation_matricies(hand_index_finger_mcp_vector,
            #                                                                body_index_finger_vector)
            # handler.rotate(rotation=index_finger_rotation_matricies,
            #                component_name=f"{side}_hand")
            #
            # hand_pinky_finger_mcp_frame_xyz = handler.trajectories[f"{side}_hand_pinky_mcp"]
            # body_hand_pinky_frame_xyz = handler.trajectories[f"{side}_pinky"]
            # hand_pinky_finger_mcp_vector = hand_pinky_finger_mcp_frame_xyz - hand_wrist_frame_xyz
            # body_pinky_finger_vector = body_hand_pinky_frame_xyz - hand_wrist_frame_xyz
            #
            # # Calculate rotation matrix to align pinky finger
            # pinky_finger_rotation_matricies = calculate_rotation_matricies(hand_pinky_finger_mcp_vector,
            #                                                                body_pinky_finger_vector)
            # handler.rotate(rotation=pinky_finger_rotation_matricies,
            #                component_name=f"{side}_hand")

        handler.mark_processing_stage("fixed_hand_data")
        logger.success("Finished fixing hand data!")
        return handler
    except Exception as e:
        logger.error(f"Error while fixing hand data:\n error:\n {e}")
        logger.exception(e)
        raise e


def calculate_rotation_matricies(data1_frame_xyz: np.ndarray,
                                 data2_frame_xyz: np.ndarray) -> List[np.ndarray]:
    """
    find the rotation matrix that rotates data1_frame_name_xyz to data2_frame_name_xyz on each frame (i.e. dimension 1)
    """
    if data1_frame_xyz.shape != data2_frame_xyz.shape:
        raise Exception(
            f"Error while calculating rotation matrix: data1_frame_name_xyz.shape != data2_frame_name_xyz.shape: {data1_frame_xyz.shape} != {data2_frame_xyz.shape}")

    rotation_matricies = []
    try:
        for frame_number in range(data1_frame_xyz.shape[0]):
            data1_xyz = data1_frame_xyz[frame_number, :]
            data2_xyz = data2_frame_xyz[frame_number, :]
            rotation_matrix = calculate_rotation_matrix(data1_xyz, data2_xyz)
            rotation_matricies.append(rotation_matrix)
    except Exception as e:
        logger.error(f"Error while calculating rotation matrix on frame_number `{frame_number}`:\n error:\n {e}")
        logger.exception(e)
        raise e
    return rotation_matricies


def calculate_rotation_matrix(data1_frame_xyz: np.ndarray,
                              data2_frame_xyz: np.ndarray) -> np.ndarray:
    if data1_frame_xyz.shape != data2_frame_xyz.shape:
        raise Exception(
            f"Error while calculating rotation matrix: data1_frame_xyz.shape != data2_frame_xyz.shape: {data1_frame_xyz.shape} != {data2_frame_xyz.shape}")
    if data1_frame_xyz.shape != (3,):
        raise Exception(
            f"Error while calculating rotation matrix: data1_frame_xyz.shape != (3,): {data1_frame_xyz.shape} != (3,)")

    data1_frame_xyz = data1_frame_xyz / np.linalg.norm(data1_frame_xyz)
    data2_frame_xyz = data2_frame_xyz / np.linalg.norm(data2_frame_xyz)
    skew_symmetric_cross_product = np.array([[0, -data1_frame_xyz[2], data1_frame_xyz[1]],
                                             [data1_frame_xyz[2], 0, -data1_frame_xyz[0]],
                                             [-data1_frame_xyz[1], data1_frame_xyz[0], 0]])
    rotation_matrix = np.eye(3) + skew_symmetric_cross_product + dot(skew_symmetric_cross_product,
                                                                     skew_symmetric_cross_product) * (
                              (1 - np.dot(data1_frame_xyz, data2_frame_xyz)) / (
                              np.linalg.norm(np.cross(data1_frame_xyz, data2_frame_xyz)) ** 2))
    return rotation_matrix
