import math

import cbor2
import numpy as np
import pytest

from freemocap_stream import (
    OVERLAY_2D,
    channel_block,
    connection_group,
    encode_frame_message,
    tracker_observation,
    uncalibrated_camera,
)


def test_channel_rows_pack_as_little_endian_row_major_float32():
    block = channel_block(OVERLAY_2D, ("x", "y", "visibility"), [[1.5, 2.0, 1.0], [math.nan, 4.0, 0.0]],
                          names=("nose", "left_eye"), camera_id="oak", image_size=(640, 480))
    assert list(block) == ["kind", "columns", "data", "camera_id", "names", "image_size"]
    values = np.frombuffer(block["data"], dtype="<f4").reshape(2, 3)
    assert values[0].tolist() == [1.5, 2.0, 1.0] and math.isnan(values[1, 0]) and values[1, 1:].tolist() == [4.0, 0.0]
    assert block["image_size"] == [640, 480] and block["names"] == ["nose", "left_eye"]


def test_channel_shape_must_match_its_columns_and_names():
    with pytest.raises(ValueError, match="shape"):
        channel_block(OVERLAY_2D, ("x", "y"), [[1.0, 2.0, 3.0]])
    with pytest.raises(ValueError, match="names"):
        channel_block(OVERLAY_2D, ("x", "y"), [[1.0, 2.0]], names=("a", "b"))
    with pytest.raises(ValueError, match="one value per row"):
        channel_block(OVERLAY_2D, ("x", "y"), [[1.0, 2.0]], sample_status=[1, 1])


def test_an_uncalibrated_camera_streams_without_3d():
    camera = uncalibrated_camera("oak", 0, (640, 480))
    assert camera["match_kind"] == "unmatched" and camera["intrinsics"] is None and camera["extrinsics"] is None
    assert camera["image_size"] == [640, 480]


def test_trackers_without_a_model_carry_their_own_connection_groups():
    body = connection_group("body", [("nose", "left_eye")], "#00ff88")
    observation = tracker_observation("yolov8_pose", [], connection_groups=[body])
    assert observation == {"tracker_id": "yolov8_pose", "detector_type": "yolov8_pose", "model_id": None,
                           "channels": [], "connection_groups": [{"name": "body", "pairs": [["nose", "left_eye"]], "color": "#00ff88"}]}
    assert "connection_groups" not in tracker_observation("other", [])


def test_frame_messages_follow_freemocaps_field_order_and_envelope():
    decoded = cbor2.loads(encode_frame_message(frame_number=12, timestamp=3.25, cameras=[uncalibrated_camera("oak", 0, (4, 2))],
                                               image=memoryview(b"payload")))
    assert list(decoded) == ["kind", "version", "timestamp", "sequence", "frame_number", "model_sequence",
                             "convention", "cameras", "models", "instances", "trackers", "image"]
    assert (decoded["kind"], decoded["sequence"], decoded["frame_number"], decoded["timestamp"]) == ("frame", 12, 12, 3.25)
    assert decoded["image"] == b"payload"
    assert "image" not in cbor2.loads(encode_frame_message(frame_number=1, timestamp=0.0, cameras=[]))
