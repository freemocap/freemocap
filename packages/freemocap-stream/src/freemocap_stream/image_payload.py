"""SkellyCam's multi-camera image payload: the bytes a frame message carries in `image`.

SkellyCam owns the layout (skellycam/core/types/frontend_payload_bytearray.py):
little-endian numpy structs with align=True padding. A 24-byte payload header
(message type 0, frame number, camera count) is followed, for each camera, by a
56-byte header (message type 1, frame number, 16-byte ASCII camera ID, camera
index, width, height, color channels, JPEG length) and that camera's JPEG bytes,
then a footer repeating the payload header with message type 2.

SkellyCam's encoder also resizes and JPEG-encodes BGR images with OpenCV. This
writer takes JPEGs the application already encoded, with any library.
"""
from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass

PAYLOAD_HEADER = struct.Struct("<B7xqi4x")
IMAGE_HEADER = struct.Struct("<B7xq16siiiii4x")
PAYLOAD_HEADER_TYPE = 0
IMAGE_HEADER_TYPE = 1
PAYLOAD_FOOTER_TYPE = 2

Bytes = bytes | bytearray | memoryview


@dataclass(frozen=True, slots=True)
class PayloadImage:
    """One camera's encoded JPEG with the identity and pixel size clients see."""

    camera_id: str
    camera_index: int
    width: int
    height: int
    jpeg: Bytes
    color_channels: int = 3

    def __post_init__(self) -> None:
        if not self.camera_id.isascii() or not 1 <= len(self.camera_id) <= 16 or "\0" in self.camera_id:
            raise ValueError(f"Camera ID {self.camera_id!r} must be 1-16 non-null ASCII characters")
        if self.camera_index < 0:
            raise ValueError("Camera index must be nonnegative")
        if self.width < 1 or self.height < 1:
            raise ValueError("Image width and height must be positive")
        if memoryview(self.jpeg).nbytes < 1:
            raise ValueError(f"Camera {self.camera_id} has no JPEG bytes")


def encode_image_payload(frame_number: int, images: Sequence[PayloadImage]) -> bytes:
    """Pack one synchronized group of JPEGs, all belonging to `frame_number`."""
    if frame_number < 0:
        raise ValueError("Frame number must be nonnegative")
    if not images:
        raise ValueError("An image payload needs at least one image")
    if len({image.camera_id for image in images}) != len(images):
        raise ValueError("Camera IDs in one payload must be unique")
    if len({image.camera_index for image in images}) != len(images):
        raise ValueError("Camera indices in one payload must be unique")
    parts: list[Bytes] = [PAYLOAD_HEADER.pack(PAYLOAD_HEADER_TYPE, frame_number, len(images))]
    for image in images:
        jpeg = memoryview(image.jpeg).cast("B")
        parts.append(IMAGE_HEADER.pack(
            IMAGE_HEADER_TYPE, frame_number, image.camera_id.encode("ascii"), image.camera_index,
            image.width, image.height, image.color_channels, len(jpeg),
        ))
        parts.append(jpeg)
    parts.append(PAYLOAD_HEADER.pack(PAYLOAD_FOOTER_TYPE, frame_number, len(images)))
    return b"".join(parts)
