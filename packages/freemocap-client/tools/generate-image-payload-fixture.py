"""Write an image payload encoded by SkellyCam's own encoder for the reader tests.

Requires an environment with SkellyCam installed (FreeMoCap's works) and writes only
the requested output file. The expected values in the JavaScript test are authored
separately from the request below, not copied from reader output.

    python tools/generate-image-payload-fixture.py tests/fixtures/image-payload.json
"""
import base64
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from skellycam.core.types.frontend_payload_bytearray import (
    ImagePayloadFrame,
    ImagePayloadRequest,
    encode_image_payload,
)


def solid(height: int, width: int, bgr: tuple[int, int, int]) -> np.ndarray:
    return np.full((height, width, 3), bgr, dtype=np.uint8)


# Two cameras with distinct IDs, non-consecutive indices and different sizes. The
# second image is resized by the encoder, as display-size hints do.
request = ImagePayloadRequest(
    frames=(
        ImagePayloadFrame(transport_id="oak", transport_index=0, frame_number=41, timestamp=10.0,
                          image=solid(8, 16, (0, 0, 255)), output_width=16, output_height=8),
        ImagePayloadFrame(transport_id="zed-left", transport_index=3, frame_number=41, timestamp=10.5,
                          image=solid(16, 16, (255, 0, 0)), output_width=8, output_height=8),
    ),
    jpeg_encoding_parameters=(int(cv2.IMWRITE_JPEG_QUALITY), 90),
)
_, _, payload = encode_image_payload(request)
fixture = {
    "source": "skellycam.core.types.frontend_payload_bytearray.encode_image_payload",
    "payload_base64": base64.b64encode(bytes(payload)).decode("ascii"),
}
Path(sys.argv[1]).write_text(json.dumps(fixture, indent=1) + "\n", encoding="utf-8")
