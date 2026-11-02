# freemocap-stream

Send FreeMoCap's self-describing WebSocket stream from any Python server, so a
browser using [`@freemocap/client`](../freemocap-client) receives your camera
video, 2D keypoints and application state through the same machinery FreeMoCap
uses. It depends only on `cbor2` and `numpy`: no FreeMoCap, SkellyCam, OpenCV or
web framework.

```sh
uv add "freemocap-stream @ git+https://github.com/freemocap/freemocap@sfn26-ultraskelly#subdirectory=packages/freemocap-stream"
```

## What travels

Every message is one CBOR map whose envelope (`kind`, `version`, `timestamp`,
`sequence`) comes first, followed by its payload. Each message carries everything
needed to interpret it: a client that joins late or reconnects needs no handshake
and no earlier message.

- **Frames** use FreeMoCap's `frame` kind, so `TransportService` resolves their
  overlays and hands over their images unchanged. A frame names its coordinate
  convention and every camera, and carries this frame's tracker observations and
  one image payload.
- **Images** travel as SkellyCam's multi-camera image payload: one JPEG per camera
  with its ID, index and pixel size. SkellyCam owns that layout; this package
  writes it from JPEGs you encoded with any library.
- **Numbers** travel as channel blocks: rows of named float32 components, packed
  little-endian and row-major, with NaN for missing values. Per-camera 2D keypoints
  use the `OVERLAY_2D` kind with columns `x`, `y`, `visibility` in image pixels.
- **Application state** uses kinds you define (for example `robot_state`), which
  the browser registers with `new TransportService({url, kinds})`.

```python
import cv2
from freemocap_stream import (
    OVERLAY_2D, PayloadImage, channel_block, connection_group, encode_frame_message,
    encode_image_payload, encode_message, tracker_observation, uncalibrated_camera,
)

ok, jpeg = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
height, width = frame_bgr.shape[:2]
frame_message = encode_frame_message(
    frame_number=frame_number,
    timestamp=capture_time,
    cameras=[uncalibrated_camera("oak", 0, (width, height))],
    trackers=[tracker_observation(
        "yolov8_pose",
        [channel_block(OVERLAY_2D, ("x", "y", "visibility"), keypoints_xyv,
                       names=keypoint_names, camera_id="oak", image_size=(width, height))],
        connection_groups=[connection_group("body", skeleton_pairs, "#00e5a0")],
    )],
    image=encode_image_payload(frame_number, [PayloadImage("oak", 0, width, height, jpeg)]),
)
state_message = encode_message("robot_state", {"servos": {"pan": 90.0}}, timestamp=now, sequence=tick)
```

Send both as binary WebSocket messages. The output matches FreeMoCap's and
SkellyCam's encoders byte for byte; `tests/test_conformance.py` checks that
wherever FreeMoCap and SkellyCam are installed.

## Development

```sh
uv run --group dev python -m pytest
```

The conformance tests skip unless FreeMoCap and SkellyCam import. From the
FreeMoCap checkout, after `uv sync --locked --group dev`:

```sh
uv run --no-sync --with-editable ../packages/freemocap-stream python -m pytest ../packages/freemocap-stream/tests
```
