"""
Create Charuco board overlay topology with configurable visualization options.
"""

import numpy as np

from freemocap.core.tasks.calibration_task.image_overlay_system import (OverlayTopology,
                                                                        ComputedPoint,
                                                                        PointElement,
                                                                        LineElement,
                                                                        TextElement,
                                                                        PointStyle,
                                                                        LineStyle,
                                                                        TextStyle,
                                                                        )


def create_charuco_topology(
        *,
        width: int,
        height: int,
        show_charuco_corners: bool = True,
        show_charuco_ids: bool = True,
        show_aruco_markers: bool = True,
        show_aruco_ids: bool = True,
        show_board_outline: bool = True,
        max_charuco_corners: int = 100,
        max_aruco_markers: int = 30,
) -> OverlayTopology:
    """
    Create a Charuco board overlay topology.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        show_charuco_corners: Show detected Charuco corner points
        show_charuco_ids: Show Charuco corner ID labels
        show_aruco_markers: Show detected ArUco marker outlines
        show_aruco_ids: Show ArUco marker ID labels
        show_board_outline: Connect detected corners to show board outline
        max_charuco_corners: Maximum number of Charuco corners to support
        max_aruco_markers: Maximum number of ArUco markers to support
    
    Returns:
        Configured OverlayTopology instance
    """
    topology = OverlayTopology(
        name="charuco_board_tracking",
        width=width,
        height=height,
        required_points=[]
    )

    # === CHARUCO CORNERS ===

    if show_charuco_corners:
        charuco_style = PointStyle(
            radius=5,
            fill='rgb(0, 255, 0)',  # Green
            stroke='rgb(0, 150, 0)',
            stroke_width=2,
            opacity=1.0
        )

        for corner_id in range(max_charuco_corners):
            topology.add(
                element=PointElement(
                    name=f"charuco_corner_{corner_id}",
                    point_name=('charuco', f'charuco_{corner_id}'),
                    style=charuco_style,
                    label=str(corner_id) if show_charuco_ids else None,
                    label_offset=(8, -8),
                    label_style=TextStyle(
                        font_size=10,
                        font_family='Arial, sans-serif',
                        fill='rgb(0, 255, 0)',
                        stroke='black',
                        stroke_width=2,
                        text_anchor='start'
                    )
                )
            )

    # === ARUCO MARKERS ===

    if show_aruco_markers:
        aruco_line_style = LineStyle(
            stroke='rgb(255, 100, 0)',  # Orange
            stroke_width=3,
            opacity=0.9
        )

        aruco_corner_style = PointStyle(
            radius=4,
            fill='rgb(255, 150, 0)',
            stroke='rgb(200, 80, 0)',
            stroke_width=1,
            opacity=1.0
        )

        for marker_id in range(max_aruco_markers):
            # Draw 4 corners
            for corner_idx in range(4):
                topology.add(
                    element=PointElement(
                        name=f"aruco_{marker_id}_corner_{corner_idx}",
                        point_name=('aruco', f'aruco_{marker_id}_corner_{corner_idx}'),
                        style=aruco_corner_style
                    )
                )

            # Draw lines connecting corners (forming square)
            connections = [
                (0, 1), (1, 2), (2, 3), (3, 0)
            ]

            for idx, (corner_a, corner_b) in enumerate(connections):
                topology.add(
                    element=LineElement(
                        name=f"aruco_{marker_id}_line_{idx}",
                        point_a=('aruco', f'aruco_{marker_id}_corner_{corner_a}'),
                        point_b=('aruco', f'aruco_{marker_id}_corner_{corner_b}'),
                        style=aruco_line_style
                    )
                )

            # Add marker ID label at center
            if show_aruco_ids:
                def compute_aruco_center(points: dict[str, dict[str, np.ndarray]],
                                         mid: int = marker_id) -> np.ndarray:
                    """Compute center of ArUco marker from its 4 corners."""
                    if 'aruco' not in points:
                        return np.array([np.nan, np.nan])

                    corners = []
                    for corner_idx in range(4):
                        corner_name = f'aruco_{mid}_corner_{corner_idx}'
                        if corner_name in points['aruco']:
                            corners.append(points['aruco'][corner_name])

                    if not corners:
                        return np.array([np.nan, np.nan])

                    stacked = np.stack(arrays=corners, axis=0)
                    return np.nanmean(a=stacked, axis=0)

                topology.computed_points.append(
                    ComputedPoint(
                        data_type='computed',
                        name=f'aruco_{marker_id}_center',
                        computation=lambda pts, mid=marker_id: compute_aruco_center(pts, mid),
                        description=f"Center of ArUco marker {marker_id}"
                    )
                )

                topology.add(
                    element=TextElement(
                        name=f"aruco_{marker_id}_label",
                        point_name=('computed', f'aruco_{marker_id}_center'),
                        text=str(marker_id),
                        offset=(0, 0),
                        style=TextStyle(
                            font_size=14,
                            font_family='Arial, sans-serif',
                            fill='rgb(255, 255, 255)',
                            stroke='rgb(255, 100, 0)',
                            stroke_width=3,
                            font_weight='bold',
                            text_anchor='start'
                        )
                    )
                )

    # === FRAME INFO ===

    topology.computed_points.append(
        ComputedPoint(
            data_type='computed',
            name='info_corner',
            computation=lambda pts: np.array([10.0, 25.0]),
            description="Top-left corner for info text"
        )
    )

    def format_charuco_info(metadata: dict[str, object]) -> str:
        """Generate dynamic frame info text."""
        frame_idx = metadata.get('frame_idx', 0)
        total_frames = metadata.get('total_frames', 0)
        n_charuco = metadata.get('n_charuco_detected', 0)
        n_charuco_total = metadata.get('n_charuco_total', 0)
        n_aruco = metadata.get('n_aruco_detected', 0)
        n_aruco_total = metadata.get('n_aruco_total', 0)
        has_pose = metadata.get('has_pose', False)
        pose_str = " | POSE ✓" if has_pose else ""

        return (f"Frame: {frame_idx}/{total_frames} | "
                f"Charuco: {n_charuco}/{n_charuco_total} | "
                f"ArUco: {n_aruco}/{n_aruco_total}{pose_str}")

    topology.add(
        element=TextElement(
            name="frame_info",
            point_name=('computed', 'info_corner'),
            text=format_charuco_info,
            offset=(0, 0),
            style=TextStyle(
                font_size=16,
                font_family='Consolas, monospace',
                fill='white',
                stroke='black',
                stroke_width=2,
                text_anchor='start'
            )
        )
    )

    # === DETECTION STATUS ===

    topology.computed_points.append(
        ComputedPoint(
            data_type='computed',
            name='status_corner',
            computation=lambda pts: np.array([10.0, 55.0]),
            description="Status text position"
        )
    )

    def format_status(metadata: dict[str, object]) -> str:
        """Generate status message."""
        n_charuco = metadata.get('n_charuco_detected', 0)
        n_aruco = metadata.get('n_aruco_detected', 0)

        if n_charuco == 0 and n_aruco == 0:
            return "⚠ NO BOARD DETECTED"
        elif n_charuco < 4:
            return "⚠ INSUFFICIENT CORNERS"
        else:
            return "✓ BOARD DETECTED"

    topology.add(
        element=TextElement(
            name="status_info",
            point_name=('computed', 'status_corner'),
            text=format_status,
            offset=(0, 0),
            style=TextStyle(
                font_size=14,
                font_family='Arial, sans-serif',
                fill='rgb(0, 255, 0)',
                stroke='black',
                stroke_width=2,
                text_anchor='start'
            )
        )
    )

    return topology
