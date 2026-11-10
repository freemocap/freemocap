"""Write messages encoded by the freemocap-stream Python package for the SDK's
cross-language test: one frame (an uncalibrated camera, 2D keypoints without a
model, a connection group and an image payload) and one application message.

Needs freemocap-stream and OpenCV, for example in FreeMoCap's environment:
    uv run --no-sync --with-editable packages/freemocap-stream python \
        packages/freemocap-client/tools/generate-python-stream-fixture.py \
        packages/freemocap-client/tests/fixtures/python-stream.json
Expected values in the JavaScript test are authored separately.
"""
import base64
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from freemocap_stream import (
    OVERLAY_2D,
    PayloadImage,
    channel_block,
    connection_group,
    encode_frame_message,
    encode_image_payload,
    encode_message,
    tracker_observation,
    uncalibrated_camera,
)

keypoints = np.array([[32.5, 20.25, 0.9], [30.0, 18.0, np.nan], [34.0, 18.0, 0.8]], dtype=np.float32)
names = ("nose", "left_eye", "right_eye")
jpeg = cv2.imencode(".jpg", np.full((48, 64, 3), (0, 0, 255), np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 80])[1]
frame = encode_frame_message(
    frame_number=41,
    timestamp=10.25,
    cameras=[uncalibrated_camera("oak", 0, (64, 48))],
    trackers=[tracker_observation(
        "yolov8_pose",
        [channel_block(OVERLAY_2D, ("x", "y", "visibility"), keypoints, names=names, camera_id="oak", image_size=(64, 48))],
        connection_groups=[connection_group("face", [("nose", "left_eye"), ("nose", "right_eye")], "#00e5a0")],
    )],
    image=encode_image_payload(41, [PayloadImage("oak", 0, 64, 48, jpeg)]),
)
state = encode_message("robot_state", {"servos": {"pan": 90.0, "tilt": 12.5}, "target": None}, timestamp=10.3, sequence=7)
fixture = {
    "source": "freemocap_stream (packages/freemocap-stream)",
    "frame_base64": base64.b64encode(frame).decode("ascii"),
    "robot_state_base64": base64.b64encode(state).decode("ascii"),
}
Path(sys.argv[1]).write_text(json.dumps(fixture, indent=1) + "\n", encoding="utf-8")
