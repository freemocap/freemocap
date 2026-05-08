"""Binary wire format for the keypoints websocket message.

Sibling to skellycam's `frontend_payload_bytearray` (which carries JPEG image
frames). The message payload looks like:

    PAYLOAD_HEADER (24B)
        message_type      u1   = MessageType.KEYPOINTS_PAYLOAD_HEADER
        frame_number      i8
        num_blocks        u4

    For each block:
      BLOCK_HEADER (44B)
        message_type      u1   = MessageType.KEYPOINTS_BLOCK_HEADER
        block_kind        u1   = BlockKind.*
        dtype_code        u1   = Dtype.FLOAT32 | FLOAT64
        dims              u1   = 2 or 3
        camera_id         S16  (zero-padded; empty for 3D blocks)
        tracker_id        S16  (matches the key in TrackerSchemasMessage.schemas)
        num_points        u4
        data_byte_length  u4   = num_points * (dims + 1) * sizeof(dtype)

      BLOCK_DATA           interleaved [x, y, (z,) visibility] per point,
                           row-major, length == data_byte_length

    PAYLOAD_FOOTER (24B)   mirrors PAYLOAD_HEADER for integrity check
        message_type      u1   = MessageType.KEYPOINTS_PAYLOAD_FOOTER
        frame_number      i8
        num_blocks        u4

The block array layout has visibility as a 4th column so the frontend can take
a single `Float32Array` view per block and index `arr[i*4 + 0..3]` directly.
For points that did not triangulate, the row is filled with NaN and visibility
is 0.

Message-type byte values are chosen to NOT collide with skellycam's image
protocol (which uses 0, 1, 2) so the frontend can demultiplex on the first
byte of any inbound binary frame.
"""
from enum import IntEnum

import numpy as np


class MessageType(IntEnum):
    KEYPOINTS_PAYLOAD_HEADER = 3
    KEYPOINTS_BLOCK_HEADER = 4
    KEYPOINTS_PAYLOAD_FOOTER = 5


class BlockKind(IntEnum):
    KEYPOINTS_RAW_3D = 0
    KEYPOINTS_FILTERED_3D = 1
    SKELETON_OVERLAY_2D = 2
    CHARUCO_OVERLAY_2D = 3


class Dtype(IntEnum):
    FLOAT32 = 0
    FLOAT64 = 1


_DTYPE_NUMPY: dict[Dtype, np.dtype] = {
    Dtype.FLOAT32: np.dtype("<f4"),
    Dtype.FLOAT64: np.dtype("<f8"),
}


def numpy_dtype_for(code: Dtype) -> np.dtype:
    return _DTYPE_NUMPY[code]


# Fixed-width string fields: 16 bytes is enough for camera ids (UUIDs are
# truncated client-side already) and for every tracker name in skellytracker
# (`rtmpose_wholebody`, `charuco`, etc.).
CAMERA_ID_BYTES = 16
# 32 bytes covers `rtmpose_wholebody` (17 chars) and any plausibly-named
# future tracker without truncation. Keep CAMERA_ID at 16 to match the
# skellycam image protocol's camera_id field width.
TRACKER_ID_BYTES = 32


KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE = np.dtype(
    [
        ("message_type", "<u1"),
        ("frame_number", "<i8"),
        ("num_blocks", "<u4"),
    ],
    align=True,
)


KEYPOINTS_BLOCK_HEADER_DTYPE = np.dtype(
    [
        ("message_type", "<u1"),
        ("block_kind", "<u1"),
        ("dtype_code", "<u1"),
        ("dims", "<u1"),
        ("camera_id", f"S{CAMERA_ID_BYTES}"),
        ("tracker_id", f"S{TRACKER_ID_BYTES}"),
        ("num_points", "<u4"),
        ("data_byte_length", "<u4"),
    ],
    align=True,
)


PAYLOAD_HEADER_SIZE = KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE.itemsize
PAYLOAD_FOOTER_SIZE = KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE.itemsize
BLOCK_HEADER_SIZE = KEYPOINTS_BLOCK_HEADER_DTYPE.itemsize


__all__ = (
    "MessageType",
    "BlockKind",
    "Dtype",
    "CAMERA_ID_BYTES",
    "TRACKER_ID_BYTES",
    "KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE",
    "KEYPOINTS_BLOCK_HEADER_DTYPE",
    "PAYLOAD_HEADER_SIZE",
    "PAYLOAD_FOOTER_SIZE",
    "BLOCK_HEADER_SIZE",
    "numpy_dtype_for",
)
