from typing import List, Dict, Optional


from freemocap.data_layer.skeleton_models.marker_info import MarkerInfo
from freemocap.data_layer.skeleton_models.segments import Segment, SegmentAnthropometry
from freemocap.data_layer.skeleton_models.skeleton import Skeleton


def create_marker_info(
    marker_list: List[str], virtual_markers: Optional[Dict[str, Dict[str, List]]] = None
) -> MarkerInfo:
    """
    Creates a MarkerInfo instance from a list of actual marker names and optional virtual markers.

    Parameters:
    - marker_list: A list of strings representing the names of actual markers.
    - virtual_markers: A dictionary defining virtual markers and their related data. Each key is a virtual marker name,
      and its value is another dictionary with 'marker_names' and 'marker_weights' as keys.

    Returns:
    - An instance of MarkerInfo populated with actual and, if provided, virtual markers.
    """
    marker_hub = MarkerInfo.create(marker_list=marker_list)

    if virtual_markers:
        marker_hub.add_virtual_markers(virtual_markers)
    return marker_hub


def create_skeleton_model(
    actual_markers: List[str],
    num_tracked_points: int,
    segment_connections: Optional[Dict[str, Segment]] = None,
    virtual_markers: Optional[Dict[str, Dict[str, List]]] = None,
    joint_hierarchy: Optional[Dict[str, List[str]]] = None,
    center_of_mass_info: Optional[Dict[str, SegmentAnthropometry]] = None,
) -> Skeleton:
    """
    Creates a Skeleton model that includes both actual and optionally virtual markers
    Optionally integrates segment connections, joint hierarchy, and anthro data if needed
    Parameters:
    - actual_markers: A list of strings representing the names of actual markers.
    - num_tracked_points: The number of tracked points expected in the 3D data.
    - segment_connections: Optional; A dictionary where each key is a segment name and its value is a dictionary
      with information about that segment (e.g., 'proximal', 'distal' marker names).
    - virtual_markers: Optional; a dictionary with information necessary to compute virtual markers.
    - joint_hierarchy: Optional; a dictionary with joint names as keys and lists of connected marker names as values.
    - center_of_mass_info: Optional; a dictionary containing segment mass percentages

    Returns:
    - An instance of the Skeleton class that represents the complete skeletal model including markers, segments,
      and optionally, joint hierarchy data.
    """
    marker_hub = create_marker_info(marker_list=actual_markers, virtual_markers=virtual_markers)

    skeleton_model = Skeleton(markers=marker_hub, num_tracked_points=num_tracked_points)

    if segment_connections:
        skeleton_model.add_segments(segment_connections)

    if joint_hierarchy:
        skeleton_model.add_joint_hierarchy(joint_hierarchy)

    if center_of_mass_info:
        skeleton_model.add_center_of_mass_definitions(center_of_mass_info)

    return skeleton_model
