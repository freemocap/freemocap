"""A charuco board, bundled for a run.

The second skeleton builder, and the one that proves the first was not a special case. A
board is a one-segment skeleton whose markers are its landmarks: no joints, no chains, no
anatomy, no authored rest pose, and no mapping file beyond a flag.

Everything here is derived from the board's own definition, so the 5x3 default and the
legacy 7x5 are the SAME skeleton built from different numbers - and a board a user prints
at some other size needs no code.

## Why the scale matters more than it looks

The board is authored normalized to `square_length = 1.0`, exactly as the human is
normalized to body height. Its fitted scale is therefore the MEASURED square length in
millimetres, and the user typed the true one into the calibration panel. Comparing the two
is a reconstruction-error metric that falls out of the same machinery that sizes a person,
with no board-specific code path.
"""
from __future__ import annotations

import numpy as np
from skellyforge.core.biomechanics.center_of_mass import CenterOfMassDefinitions
from skellyforge.core.skeleton.components.landmark_grouping import (
    LandmarkConnectionGroup,
    LandmarkGroup,
)
from skellyforge.core.skeleton.pose.model_scale_fitting import (
    StreamingModelScaleFitter,
    scale_voting_segment_names,
)
from skellyforge.core.skeleton.pose.rest_pose import RestPose
from skellyforge.core.skeleton.rigid_marker_skeleton import build_rigid_marker_skeleton
from skellytracker.core.detectors.keypoint_detectors.charuco.charuco_board_definition import (
    ARUCO_MARKER_TAGS,
    CHARUCO_CORNER_TAGS,
    CHARUCO_GRID_TAGS,
    CharucoBoardDefinition,
)
from skellytracker.core.io.mapping_paths import CHARUCO_BOARD_MAPPING
from skellytracker.core.io.tracker_mapping import TrackerMapping

from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle

CHARUCO_BOARD_MODEL_ID: str = "charuco_board"
CHARUCO_DETECTOR_TYPE: str = "charuco"
SQUARE_LENGTH_SCALE_REFERENCE: str = "square_length"
BOARD_SEGMENT_NAME: str = "charuco_board_plate"
BOARD_MASS: float = 1.0
"""The board's mass, in whatever units. Arbitrary, and it cancels.

A one-segment skeleton's whole-body centre of mass is its only segment's centre, so the
mass scales the weighted mean by a constant and divides straight back out. It is named
rather than inlined so nobody later reads a bare `1.0` as a measurement.
"""


def build_charuco_board_bundle(*, board: CharucoBoardDefinition) -> TrackedSkeletonBundle:
    """The charuco board this run is tracking, built from its own geometry.

    Args:
        board: the board definition the detector is configured with - the single source of
            its point names, normalized geometry and connections.
    """
    skeleton = build_rigid_marker_skeleton(
        name=CHARUCO_BOARD_MODEL_ID,
        segment_name=BOARD_SEGMENT_NAME,
        marker_positions=board.normalized_point_positions,
        # The board's own lattice fixes its frame: corner 0 is the origin, corner 1 is one
        # square along +x, and the first corner of the next row is one square along +y.
        # Named explicitly rather than picked automatically, because many triads would give
        # a valid frame and choosing one silently is how an object's axes change the day a
        # marker is added.
        origin_marker_name="CharucoCorner-0",
        primary_marker_name="CharucoCorner-1",
        secondary_marker_name=f"CharucoCorner-{board.squares_x - 1}",
        marker_definition="a fiducial marker corner on a charuco calibration board",
        landmark_groups={
            "charuco_corners": LandmarkGroup(
                name="charuco_corners",
                landmark_names=board.charuco_corner_names,
                tags=CHARUCO_CORNER_TAGS,
            ),
            "aruco_corners": LandmarkGroup(
                name="aruco_corners",
                landmark_names=board.aruco_corner_names,
                tags=ARUCO_MARKER_TAGS,
            ),
        },
        landmark_connections={
            "charuco_grid": LandmarkConnectionGroup(
                name="charuco_grid",
                pairs=board.charuco_grid_connections,
                tags=CHARUCO_GRID_TAGS,
            ),
            "aruco_markers": LandmarkConnectionGroup(
                name="aruco_markers",
                pairs=board.aruco_marker_connections,
                tags=ARUCO_MARKER_TAGS,
            ),
        },
        # No inertia (no mass model), no XCoM (a board is not balancing), and no roll
        # resolution: its one segment is fully specified, so its roll is MEASURED, and
        # applying a continuity convention would invent state over a measurement.
        derived_quantities=frozenset(),
    )
    mapping = TrackerMapping.from_yaml(
        CHARUCO_BOARD_MAPPING, known_tracker_keypoints=set(board.all_point_names)
    )
    return TrackedSkeletonBundle(
        model_id=CHARUCO_BOARD_MODEL_ID,
        detector_type=CHARUCO_DETECTOR_TYPE,
        tracker_keypoint_names=board.all_point_names,
        skeleton=skeleton,
        # Nothing to author: the markers are on the board, so the rest pose is identity.
        rest_pose=RestPose.default_for(skeleton=skeleton),
        landmark_mapping=mapping,
        # The board declares no mass model, so it gets the unweighted mean of its markers.
        center_of_mass_definitions=CenterOfMassDefinitions.default_for(skeleton=skeleton),
        segment_masses={BOARD_SEGMENT_NAME: BOARD_MASS},
        scale_reference_name=SQUARE_LENGTH_SCALE_REFERENCE,
    )
