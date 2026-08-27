"""The charuco board as a tracked skeleton, end to end onto the wire.

This is the gate on the whole generic-skeleton effort. The board exercises every place the
pipeline used to assume one human: one segment, no joints, no anatomy, its own reference
unit, landmark-level structure, and no authored mapping. If any of those assumptions came
back, something here fails.

The board is driven from its OWN geometry scaled to the square length the user entered, so
the fitted scale is checkable against a known answer — which is the reconstruction-error
metric the design is built around, exercised as a test.
"""
from __future__ import annotations

import cbor2
import numpy as np
import pytest
from skellytracker.core.detectors.keypoint_detectors.charuco.charuco_board_definition import (
    CharucoBoardDefinition,
)

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.skeletons.charuco_board_skeleton import (
    CHARUCO_BOARD_MODEL_ID,
    build_charuco_board_bundle,
)
from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.skeletons.standard_human_skeleton import STANDARD_HUMAN_MODEL_ID
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.skeletons.tracked_skeleton_set import build_tracked_skeletons
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.message_model import encode_message
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage
from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints

BOARD_WORLD_OFFSET = np.array([600.0, 300.0, 20.0])


def _board_bundle(board: CharucoBoardDefinition) -> TrackedSkeletonBundle:
    return build_charuco_board_bundle(board=board, scale_window_frames=30)


def _observed_board(
    *, bundle: TrackedSkeletonBundle, square_length_mm: float
) -> dict[str, np.ndarray]:
    """The board seen at its real size, somewhere in the room."""
    return {
        name: square_length_mm * landmark.local_position.array + BOARD_WORLD_OFFSET
        for name, landmark in bundle.skeleton.landmarks.items()
    }


# ── the board is a skeleton ────────────────────────────────────────────────


def test_a_board_is_a_one_segment_skeleton_with_no_joints() -> None:
    board = CharucoBoardDefinition.create_letter_size_5x3()
    bundle = _board_bundle(board)

    assert len(bundle.skeleton.segments) == 1
    assert bundle.skeleton.joints == {}
    assert bundle.skeleton.chains == {}
    assert len(bundle.skeleton.landmarks) == len(board.all_point_names)
    # No mass model, no balance quantities, and its roll is measured — so it opted into
    # nothing, and has no roll resolver applying a continuity convention over a fact.
    assert bundle.skeleton.derived_quantities == frozenset()
    assert bundle.roll_resolver is None


def test_a_board_needs_no_authored_mapping_or_rest_pose() -> None:
    """The two files a new object would otherwise have to bring."""
    bundle = _board_bundle(CharucoBoardDefinition.create_letter_size_5x3())

    # Pass-through: every keypoint is a landmark of the same name, so everything measures.
    assert bundle.landmark_mapping.is_passthrough
    assert bundle.landmark_mapping.directly_measured_landmark_names == frozenset(
        bundle.skeleton.landmarks
    )
    # Rest pose defaulted: the markers are on the board, so identity is the whole answer.
    assert bundle.rest_pose.parents == {"charuco_board_plate": None}


def test_a_board_gets_a_centre_of_mass_without_declaring_a_mass_model() -> None:
    bundle = _board_bundle(CharucoBoardDefinition.create_letter_size_5x3())
    observed = _observed_board(bundle=bundle, square_length_mm=54.0)

    reconstruction = reconstruct_skeleton(
        bundle=bundle, filtered_keypoints=observed, compute_center_of_mass=True
    )

    assert reconstruction is not None
    assert reconstruction.center_of_mass is not None
    # The unweighted mean of its markers, which for a flat board is on the board.
    assert reconstruction.center_of_mass[2] == pytest.approx(BOARD_WORLD_OFFSET[2])
    # No joints means no joint angles — an absent channel, not a channel of NaNs.
    assert reconstruction.joint_angles is None


# ── the scale IS the calibration's scale ───────────────────────────────────


@pytest.mark.parametrize(
    "board",
    [
        CharucoBoardDefinition.create_letter_size_5x3(),
        CharucoBoardDefinition.create_test_data_7x5(),
        CharucoBoardDefinition(squares_x=9, squares_y=7, square_length_mm=33.0),
    ],
    ids=["5x3", "7x5", "9x7"],
)
def test_the_fitted_scale_is_the_measured_square_length(
    board: CharucoBoardDefinition,
) -> None:
    """The metric the whole design is built around, and the parametric-board check.

    A board authored at `square_length = 1.0` fits to the square length the cameras
    actually see, which is directly comparable to the value the user typed at calibration.
    Three board sizes including one that is not a shipped default: the geometry is
    parametric, so a board a user prints must work with no code change.
    """
    bundle = _board_bundle(board)
    observed = _observed_board(
        bundle=bundle, square_length_mm=board.square_length_mm
    )

    reconstruction = reconstruct_skeleton(
        bundle=bundle, filtered_keypoints=observed, compute_center_of_mass=False
    )

    assert reconstruction is not None
    assert reconstruction.fitted_scale_mm == pytest.approx(
        board.square_length_mm, rel=1e-9
    )


def test_a_misprinted_board_shows_up_as_a_scale_mismatch() -> None:
    """Why the fit is worth running on an object whose size is 'known'.

    A board printed at 98% scale reconstructs perfectly well — and the fitted square
    length says so, which is the error signal.
    """
    board = CharucoBoardDefinition.create_letter_size_5x3()
    bundle = _board_bundle(board)
    actual_square_length = board.square_length_mm * 0.98

    reconstruction = reconstruct_skeleton(
        bundle=bundle,
        filtered_keypoints=_observed_board(
            bundle=bundle, square_length_mm=actual_square_length
        ),
        compute_center_of_mass=False,
    )

    assert reconstruction is not None
    assert reconstruction.fitted_scale_mm == pytest.approx(actual_square_length, rel=1e-9)
    assert reconstruction.fitted_scale_mm != pytest.approx(board.square_length_mm)


def test_a_partially_visible_board_still_reconstructs() -> None:
    """Most of the board out of frame is ordinary; three non-collinear corners suffice.

    Corners 0 and 1 are adjacent along the first row; corner `squares_x - 1` is the start
    of the second row. Three corners spanning two rows, out of thirty-six points.
    """
    board = CharucoBoardDefinition.create_letter_size_5x3()
    bundle = _board_bundle(board)
    everything = _observed_board(bundle=bundle, square_length_mm=54.0)
    visible = {
        name: everything[name]
        for name in (
            "CharucoCorner-0",
            "CharucoCorner-1",
            f"CharucoCorner-{board.squares_x - 1}",
        )
    }

    reconstruction = reconstruct_skeleton(
        bundle=bundle, filtered_keypoints=visible, compute_center_of_mass=False
    )

    assert reconstruction is not None
    assert reconstruction.fitted_scale_mm == pytest.approx(54.0, rel=1e-6)
    # Every segment gets a length, seen or not — one segment here, but the rule is general.
    assert set(reconstruction.segment_lengths) == set(bundle.skeleton.segments)


def test_a_board_seen_edge_on_reconstructs_nothing_rather_than_guessing() -> None:
    """Only one row visible is COLLINEAR, and a line fixes no pose however long you look.

    The honest answer is an absent model this frame. Worth pinning, because the tempting
    alternative — falling back to a partial or previous pose — is exactly the kind of
    quiet repair that makes a bad reconstruction look like a good one.
    """
    board = CharucoBoardDefinition.create_letter_size_5x3()
    bundle = _board_bundle(board)
    everything = _observed_board(bundle=bundle, square_length_mm=54.0)
    one_row_only = {
        name: everything[name]
        for name in board.charuco_corner_names[: board.squares_x - 1]
    }

    assert (
        reconstruct_skeleton(
            bundle=bundle,
            filtered_keypoints=one_row_only,
            compute_center_of_mass=False,
        )
        is None
    )


# ── both skeletons, on one wire ────────────────────────────────────────────


def _frame_with_a_person_and_a_board() -> dict:
    config = CameraNodeConfig()
    bundles = build_tracked_skeletons(
        camera_node_config=config, scale_window_frames=30
    )
    board_bundle = next(b for b in bundles if b.model_id == CHARUCO_BOARD_MODEL_ID)

    # One flat keypoint dict carrying BOTH detectors' output, as the aggregator publishes:
    # detector name spaces do not collide, and each mapping takes only what it recognizes.
    keypoints = dict(_standing_keypoints())
    keypoints.update(
        _observed_board(
            bundle=board_bundle, square_length_mm=config.charuco_board.square_length_mm
        )
    )

    reconstructions = {}
    for bundle in bundles:
        reconstruction = reconstruct_skeleton(
            bundle=bundle, filtered_keypoints=keypoints, compute_center_of_mass=True
        )
        if reconstruction is not None:
            reconstructions[reconstruction.model_id] = reconstruction

    composition = compose_messages(
        StreamContext(
            skeletons=bundles,
            camera_ids=("cam-0",),
            detector_type=config.detector_type,
            pipeline_live=True,
        )
    )
    frame = composition.compose_frame_message(
        FrameContext(
            frame_number=1,
            timestamp=0.0,
            aggregator_output=AggregationNodeOutputMessage(
                frame_number=1,
                pipeline_config=RealtimePipelineConfig(),
                camera_group_id="cg-0",
                camera_node_outputs={},
                keypoints_arrays=keypoints,
                reconstructions=reconstructions,
            ),
        )
    )
    return cbor2.loads(encode_message(frame))


def test_one_frame_carries_two_models_two_instances_and_two_trackers() -> None:
    """The plural wire, actually plural. Nothing here is the human's special case."""
    frame = _frame_with_a_person_and_a_board()

    assert [m["model_id"] for m in frame["models"]] == [
        STANDARD_HUMAN_MODEL_ID,
        CHARUCO_BOARD_MODEL_ID,
    ]
    assert {i["model_id"] for i in frame["instances"]} == {
        STANDARD_HUMAN_MODEL_ID,
        CHARUCO_BOARD_MODEL_ID,
    }
    assert {t["tracker_id"] for t in frame["trackers"]} == {"rtmpose", "charuco"}
    # Instance ids are distinct, so two occurrences never collide.
    assert len({i["instance_id"] for i in frame["instances"]}) == 2


def test_each_model_names_its_own_scale_unit() -> None:
    """A client renders "1684 mm tall" or "54 mm squares" without knowing which is which."""
    frame = _frame_with_a_person_and_a_board()
    by_id = {m["model_id"]: m for m in frame["models"]}
    instances = {i["model_id"]: i for i in frame["instances"]}

    assert by_id[STANDARD_HUMAN_MODEL_ID]["scale_reference_name"] == "body_height"
    assert by_id[CHARUCO_BOARD_MODEL_ID]["scale_reference_name"] == "square_length"
    assert instances[CHARUCO_BOARD_MODEL_ID]["fitted_scale_mm"] == pytest.approx(
        CameraNodeConfig().charuco_board.square_length_mm, rel=1e-6
    )
    assert 1400.0 < instances[STANDARD_HUMAN_MODEL_ID]["fitted_scale_mm"] < 2100.0


def test_the_board_ships_its_structure_so_no_client_rebuilds_it() -> None:
    """The grid and the marker quads ride the wire, coloured — no client-side derivation.

    This is what retires rebuilding the lattice from board dimensions and splitting
    `ArucoMarkerCorner-{id}-{corner}` to recover a square.
    """
    frame = _frame_with_a_person_and_a_board()
    board_model = next(
        m for m in frame["models"] if m["model_id"] == CHARUCO_BOARD_MODEL_ID
    )
    groups = {g["name"]: g for g in board_model["landmark_connections"]}

    assert set(groups) == {"charuco_grid", "aruco_markers"}
    # Green lattice, orange fiducials — the scheme the old viewer drew.
    assert groups["charuco_grid"]["color"] == "#14ff14"
    assert groups["aruco_markers"]["color"] == "#ff8c14"
    assert groups["charuco_grid"]["pairs"], "the grid must carry its edges"
    # Every edge names points the model actually has.
    known = {landmark["name"] for landmark in board_model["landmarks"]}
    for group in groups.values():
        for first, second in group["pairs"]:
            assert first in known and second in known


def test_a_board_only_session_tracks_only_the_board() -> None:
    """Turning skeleton tracking off leaves one model, not a human full of NaNs."""
    bundles = build_tracked_skeletons(
        camera_node_config=CameraNodeConfig(skeleton_tracking_enabled=False),
        scale_window_frames=30,
    )
    assert [b.model_id for b in bundles] == [CHARUCO_BOARD_MODEL_ID]
