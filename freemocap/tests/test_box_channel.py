"""The BOXES_2D channel: a detector's crop, carried to the client on every frame.

Bounding boxes are what the keypoint detector is actually cropped to. They reached the
aggregator output but were dropped before the wire, so an over-eager re-detect or a
collapsed crop was invisible until it showed up as a frame-rate cliff. These tests pin
the shape of the channel that makes it visible.
"""
from __future__ import annotations

import struct

# NOTE the import order matters: realtime_pipeline_config must NOT be the first
# freemocap import — see the note in test_full_loop.py.
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.producers.box_producer import BOX_COLUMNS
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.skeletons.charuco_board_skeleton import build_charuco_board_bundle
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.pubsub.pubsub_topics import (
    AggregationNodeOutputMessage,
    CameraNodeOutputMessage,
)

import math

from skellytracker.core.data_primitives.bounding_box import BoundingBox
from skellytracker.core.data_primitives.observation import Observation, StageObservation

CAMERA_IDS = ("cam-0", "cam-1")
FRAME_NUMBER = 7
BOX = (512.0, 18.0, 791.0, 706.0)
CONFIDENCE = 0.93


def _observation(*, with_box: bool, detector_ran: bool) -> Observation:
    return Observation(
        frame_number=FRAME_NUMBER,
        image_size=(720, 1280),
        stages={
            "body": StageObservation(
                name="body",
                bounding_boxes=(
                    [BoundingBox(x1=BOX[0], y1=BOX[1], x2=BOX[2], y2=BOX[3],
                                 confidence=CONFIDENCE)]
                    if with_box else []
                ),
                detector_ran=detector_ran,
            )
        },
    )


def _aggregator_message(*, detector_ran: bool) -> AggregationNodeOutputMessage:
    """cam-0 has a box this frame; cam-1 detected nothing."""
    return AggregationNodeOutputMessage(
        frame_number=FRAME_NUMBER,
        pipeline_config=RealtimePipelineConfig(),
        camera_group_id="cg-0",
        camera_node_outputs={
            "cam-0": CameraNodeOutputMessage(
                camera_id="cam-0",
                frame_number=FRAME_NUMBER,
                skeleton_observation=_observation(with_box=True, detector_ran=detector_ran),
            ),
            "cam-1": CameraNodeOutputMessage(
                camera_id="cam-1",
                frame_number=FRAME_NUMBER,
                skeleton_observation=_observation(with_box=False, detector_ran=False),
            ),
        },
    )


def _box_blocks(*, detector_ran: bool = False):
    composition = compose_messages(
        StreamContext(
            skeletons=(build_standard_human_bundle(detector_type="rtmpose"),),
            camera_ids=CAMERA_IDS,
            detector_type="rtmpose",
            pipeline_live=True,
            live_image_sizes={camera_id: (1280, 720) for camera_id in CAMERA_IDS},
        )
    )
    frame = composition.compose_frame_message(
        FrameContext(
            frame_number=FRAME_NUMBER,
            timestamp=0.0,
            aggregator_output=_aggregator_message(detector_ran=detector_ran),
        )
    )
    # Boxes are a tracker measurement, not a reconstruction, so they ride the tracker
    # observations rather than the model instances.
    return [
        block
        for tracker in frame.trackers
        for block in tracker.channels
        if block.kind == "BOXES_2D"
    ]


def _rows(block) -> list[tuple[float, ...]]:
    width = len(BOX_COLUMNS)
    values = struct.unpack(f"<{len(block.data) // 4}f", block.data)
    return [values[i:i + width] for i in range(0, len(values), width)]


def test_one_box_block_per_camera_with_stage_names() -> None:
    blocks = _box_blocks()
    assert [block.camera_id for block in blocks] == list(CAMERA_IDS)
    for block in blocks:
        # The declared row set comes from the detector's stages, so a camera that saw
        # nothing still reports a row rather than vanishing from the frame.
        assert block.names == ("body",)
        assert block.columns == BOX_COLUMNS
        assert block.image_size == (1280, 720)
        assert len(block.data) == len(BOX_COLUMNS) * 4


def test_box_values_survive_the_wire() -> None:
    by_camera = {block.camera_id: block for block in _box_blocks(detector_ran=True)}
    (x1, y1, x2, y2, confidence, detector_ran), = _rows(by_camera["cam-0"])
    assert (x1, y1, x2, y2) == BOX
    assert confidence == float(struct.unpack("<f", struct.pack("<f", CONFIDENCE))[0])
    assert detector_ran == 1.0


def test_absent_box_is_a_nan_row_not_a_dropped_block() -> None:
    by_camera = {block.camera_id: block for block in _box_blocks()}
    assert "cam-1" in by_camera, "a camera with no detection still needs its row"
    (row,) = _rows(by_camera["cam-1"])
    assert all(math.isnan(value) for value in row)


def test_a_detectorless_tracker_emits_no_box_block() -> None:
    """Charuco runs no object detector, so DetectionStage synthesizes a box covering the
    whole frame. A rectangle around the entire image is not a measurement, and drawing
    one on every camera is the artifact this channel exists to make visible."""
    composition = compose_messages(
        StreamContext(
            skeletons=(build_charuco_board_bundle(
                board=CharucoBoardDefinition(
                    squares_x=5, squares_y=3, square_length_mm=126.0,
                ),
            ),),
            camera_ids=CAMERA_IDS,
            detector_type="charuco",
            pipeline_live=True,
            live_image_sizes={camera_id: (1280, 720) for camera_id in CAMERA_IDS},
        )
    )
    frame = composition.compose_frame_message(
        FrameContext(
            frame_number=FRAME_NUMBER,
            timestamp=0.0,
            aggregator_output=_aggregator_message(detector_ran=False),
        )
    )
    assert not [
        block
        for tracker in frame.trackers
        for block in tracker.channels
        if block.kind == "BOXES_2D"
    ]


def test_detector_provenance_rides_along() -> None:
    """The flag the overlay colours by — green when the detector actually ran."""
    tracked, = _rows(
        {b.camera_id: b for b in _box_blocks(detector_ran=False)}["cam-0"]
    )
    detected, = _rows(
        {b.camera_id: b for b in _box_blocks(detector_ran=True)}["cam-0"]
    )
    assert tracked[-1] == 0.0
    assert detected[-1] == 1.0
