"""Byte-for-byte agreement with FreeMoCap's and SkellyCam's own encoders.

These run where FreeMoCap and SkellyCam are installed (see README) and skip elsewhere.
"""
import numpy as np
import pytest

message_model = pytest.importorskip("freemocap.core.streaming.message_model")
skellycam_payload = pytest.importorskip("skellycam.core.types.frontend_payload_bytearray")
cv2 = pytest.importorskip("cv2")
from freemocap.core.streaming.rest_geometry import ModelConnectionGroup  # noqa: E402
from freemocap.core.types.channel_kind import ChannelKind  # noqa: E402

from freemocap_stream import (  # noqa: E402
    OVERLAY_2D,
    PayloadImage,
    channel_block,
    connection_group,
    encode_frame_message,
    encode_image_payload,
    tracker_observation,
    uncalibrated_camera,
)

NAMES = ("nose", "left_eye", "right_eye")
COLUMNS = ("x", "y", "visibility")
KEYPOINTS = np.array([[32.5, 20.25, 0.9], [30.0, 18.0, np.nan], [34.0, 18.0, 0.8]], dtype=np.float32)
PAIRS = (("nose", "left_eye"), ("nose", "right_eye"))
JPEG_PARAMETERS = (int(cv2.IMWRITE_JPEG_QUALITY), 80)


def skellycam_frames():
    return (
        skellycam_payload.ImagePayloadFrame(transport_id="oak", transport_index=0, frame_number=41, timestamp=10.0,
                                            image=np.full((48, 64, 3), (0, 0, 255), np.uint8), output_width=64, output_height=48),
        skellycam_payload.ImagePayloadFrame(transport_id="zed-left", transport_index=3, frame_number=41, timestamp=10.5,
                                            image=np.full((32, 32, 3), (255, 0, 0), np.uint8), output_width=32, output_height=32),
    )


def our_image_payload() -> bytes:
    return encode_image_payload(41, [
        PayloadImage(frame.transport_id, frame.transport_index, frame.output_width, frame.output_height,
                     cv2.imencode(".jpg", frame.image, list(JPEG_PARAMETERS))[1])
        for frame in skellycam_frames()
    ])


def test_image_payload_matches_skellycams_encoder():
    _, _, expected = skellycam_payload.encode_image_payload(
        skellycam_payload.ImagePayloadRequest(skellycam_frames(), JPEG_PARAMETERS))
    assert our_image_payload() == bytes(expected)


def test_frame_message_matches_freemocaps_encoder():
    image = our_image_payload()
    ours = encode_frame_message(
        frame_number=41,
        timestamp=10.25,
        cameras=[uncalibrated_camera("oak", 0, (64, 48)), uncalibrated_camera("zed-left", 3, (32, 32))],
        trackers=[tracker_observation(
            "yolov8_pose",
            [channel_block(OVERLAY_2D, COLUMNS, KEYPOINTS, names=NAMES, camera_id="oak", image_size=(64, 48))],
            connection_groups=[connection_group("face", PAIRS, "#00e5a0")],
        )],
        image=image,
    )
    m = message_model
    theirs = m.encode_message(m.FrameMessage(
        envelope=m.MessageEnvelope(timestamp=10.25, sequence=41),
        frame_number=41,
        cameras=(
            m.CalibratedCamera.unmatched(camera_id="oak", camera_index=0, rotation=m.CameraRotation.NONE, image_size=(64, 48)),
            m.CalibratedCamera.unmatched(camera_id="zed-left", camera_index=3, rotation=m.CameraRotation.NONE, image_size=(32, 32)),
        ),
        trackers=(m.TrackerObservation(
            tracker_id="yolov8_pose",
            detector_type="yolov8_pose",
            model_id=None,
            channels=(m.ChannelBlock(kind=ChannelKind.OVERLAY_2D, columns=COLUMNS, data=KEYPOINTS.astype("<f4").tobytes(),
                                     camera_id="oak", names=NAMES, image_size=(64, 48)),),
            connection_groups=(ModelConnectionGroup(name="face", pairs=PAIRS, color="#00e5a0"),),
        ),),
        image=memoryview(image),
    ))
    assert ours == theirs
