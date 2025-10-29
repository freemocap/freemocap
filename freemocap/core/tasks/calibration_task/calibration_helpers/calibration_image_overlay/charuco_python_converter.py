"""
Convert CharucoObservation to overlay-compatible data format.
"""

from typing import Any
import numpy as np
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation


def charuco_observation_to_overlay_data(
    observation: CharucoObservation
) -> dict[str, dict[str, np.ndarray]]:
    """
    Convert CharucoObservation to overlay points format.
    
    Returns nested dict: {data_type: {point_name: [x, y]}}
    
    Structure:
        - 'charuco': Charuco corner points (charuco_0, charuco_1, ...)
        - 'aruco': ArUco marker corners (aruco_0_corner_0, aruco_0_corner_1, ...)
    """
    points: dict[str, dict[str, np.ndarray]] = {
        'charuco': {},
        'aruco': {}
    }
    
    # Add detected Charuco corners
    if not observation.charuco_empty:
        for corner_id, corner_coords in observation.charuco_corners_dict.items():
            points['charuco'][f'charuco_{corner_id}'] = corner_coords
    
    # Add detected ArUco marker corners
    if not observation.aruco_empty:
        for marker_id, marker_corners in observation.aruco_corners_dict.items():
            # ArUco markers have 4 corners
            for corner_idx in range(4):
                corner_name = f'aruco_{marker_id}_corner_{corner_idx}'
                points['aruco'][corner_name] = marker_corners[corner_idx]
    
    return points


def charuco_observation_to_metadata(
    observation: CharucoObservation,
    total_frames: int | None = None
) -> dict[str, Any]:
    """
    Extract metadata from CharucoObservation for display.
    """
    metadata: dict[str, Any] = {
        'frame_idx': observation.frame_number,
        'total_frames': total_frames or 0,
        'n_charuco_detected': 0 if observation.charuco_empty else len(observation.detected_charuco_corner_ids),
        'n_charuco_total': len(observation.all_charuco_ids),
        'n_aruco_detected': 0 if observation.aruco_empty else len(observation.detected_aruco_marker_ids),
        'n_aruco_total': len(observation.all_aruco_ids),
        'image_width': observation.image_size[0],
        'image_height': observation.image_size[1],
    }
    
    # Add pose info if available
    if observation.charuco_board_translation_vector is not None:
        metadata['has_pose'] = True
        metadata['translation'] = observation.charuco_board_translation_vector.tolist()
        metadata['rotation'] = observation.charuco_board_rotation_vector.tolist()
    else:
        metadata['has_pose'] = False
    
    return metadata


def stream_charuco_observations(
    observations: list[CharucoObservation]
) -> tuple[list[dict[str, dict[str, np.ndarray]]], list[dict[str, Any]]]:
    """
    Convert a list of observations to overlay format for batch processing.
    
    Returns:
        tuple of (points_list, metadata_list)
    """
    points_list = []
    metadata_list = []
    
    total_frames = len(observations)
    
    for obs in observations:
        points = charuco_observation_to_overlay_data(obs)
        metadata = charuco_observation_to_metadata(obs, total_frames)
        
        points_list.append(points)
        metadata_list.append(metadata)
    
    return points_list, metadata_list


# Example usage with your existing code:
"""
from .image_overlay_system import overlay_image
from create_charuco_topology import create_charuco_topology

# Setup topology once
topology = create_charuco_topology(
    width=1920,
    height=1080,
    show_charuco_corners=True,
    show_charuco_ids=True,
    show_aruco_markers=True,
    show_aruco_ids=True
)

# For each frame
observation: CharucoObservation = ...  # Your detection result

# Convert to overlay format
points = charuco_observation_to_overlay_data(observation)
metadata = charuco_observation_to_metadata(observation, total_frames=1000)

# Render
annotated_frame = overlay_image(
    image=frame,
    topology=topology,
    points=points,
    metadata=metadata
)
"""
