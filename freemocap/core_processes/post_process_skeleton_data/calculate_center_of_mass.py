import logging
from typing import Dict, Tuple
import numpy as np

from freemocap.data_layer.skeleton_models.segments import SegmentAnthropometry
from freemocap.data_layer.skeleton_models.skeleton import Skeleton

logger = logging.getLogger(__name__)


def calculate_all_segments_com(
    segment_positions: Dict[str, Dict[str, np.ndarray]], center_of_mass_definitions: Dict[str, SegmentAnthropometry]
) -> Dict[str, np.ndarray]:
    """
    Calculates the center of mass (COM) for each segment based on provided segment positions
    and anthropometric data.

    Parameters:
    - segment_positions: A dictionary where each key is a segment name, and the value is another
      dictionary with 'proximal' and 'distal' keys containing the respective marker positions
      as numpy arrays.
    - center_of_mass_definitions: A dictionary containing anthropometric information for each segment.
      Each key is a segment name with a value that is a dictionary, which includes the
      'segment_com_length' key representing the percentage distance from the proximal marker
      to the segment's COM.

    Returns:
    - A dictionary where each key is a segment name, and the value is the calculated COM
      position as a numpy array.
    """

    segment_com_data = {}

    for segment_name, segment_info in center_of_mass_definitions.items():
        proximal = segment_positions[segment_name]["proximal"]
        distal = segment_positions[segment_name]["distal"]

        com_length = segment_info.segment_com_length

        segment_com = proximal + (distal - proximal) * com_length

        segment_com_data[segment_name] = segment_com

    return segment_com_data


def calculate_total_body_center_of_mass(
    segment_center_of_mass_data: Dict[str, np.ndarray],
    center_of_mass_definitions: Dict[str, SegmentAnthropometry],
    num_frames: int,
) -> np.ndarray:
    """
    Calculates the total body center of mass for each frame based on segment COM positions and anthropometric data.

    Parameters:
    - segment_com_data: A dictionary with segment names as keys and COM positions as values for each frame.
    - center_of_mass_definitions: A dictionary containing segment mass percentages.
    - num_frames: The number of frames in the data.

    Returns:
    - A numpy array containing the position of the total body center of mass for each frame.
    """
    total_body_com = np.zeros((num_frames, 3))

    for segment_name, segment_info in center_of_mass_definitions.items():

        segment_com = segment_center_of_mass_data.get(segment_name)
        if segment_com is None:
            raise ValueError(f"Segment {segment_name} not found in segment center of mass data.")

        segment_mass_percentage = segment_info.segment_com_percentage

        total_body_com += segment_com * segment_mass_percentage

    return total_body_com


def get_all_segment_markers(skeleton: Skeleton) -> Dict[str, Dict[str, np.ndarray]]:
    """
    Retrieves the proximal and distal marker positions for all segments within a skeleton.

    Parameters:
    - skeleton: The Skeleton instance containing segment information and marker data.

    Returns:
    - A dictionary where each key is a segment name, and the value is another dictionary
      with 'proximal' and 'distal' keys containing the respective marker positions as numpy arrays.
    """
    segment_positions = {}

    if skeleton.segments is None:
        raise ValueError("Segments must be defined before getting segment markers.")

    for segment_name in skeleton.segments.keys():
        segment_positions[segment_name] = skeleton.get_segment_markers(segment_name)

    return segment_positions


def merge_segment_com_data(segment_com_data: Dict[str, np.ndarray]) -> np.ndarray:
    """
    Merges the center of mass data from multiple segments into a single array.

    Parameters:
    - segment_com_data: A dictionary where each key is a segment name and the value is the center of mass data for that segment.

    Returns:
    - A numpy array containing the merged center of mass data.
    """
    com_data_list = list(segment_com_data.values())

    return np.stack(com_data_list, axis=1)


def calculate_center_of_mass_from_skeleton(skeleton: Skeleton) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculates the segment and total body center of mass for a skeleton based on anthropometric data.

    Parameters:
    - skeleton: The Skeleton instance containing marker data and segment information.
    - anthropometric_data: A dictionary containing segment mass percentages

    Returns:
    - A tuple containing the segment center of mass data and the total body center of mass.
    """
    if skeleton.center_of_mass_definitions is None:
        raise ValueError("Segment center of mass definitions must be defined before calculating center of mass.")

    if skeleton.segments is None:
        raise ValueError("Segments must be defined before calculating center of mass.")

    segment_3d_positions = get_all_segment_markers(skeleton)  # TODO: Should this be a method of the skeleton model?
    segment_com_data = calculate_all_segments_com(segment_3d_positions, skeleton.center_of_mass_definitions)
    total_body_com = calculate_total_body_center_of_mass(
        segment_com_data, skeleton.center_of_mass_definitions, skeleton.num_frames
    )

    merged_segment_com_data = merge_segment_com_data(segment_com_data)

    return merged_segment_com_data, total_body_com
