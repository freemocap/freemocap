"""Build the binary keypoints websocket message from aggregation output.

The wire format is documented in `freemocap.api.websocket.binary_keypoints_protocol`.

This module:
  * Densifies the sparse `dict[name, ndarray(3,)]` from the aggregator into a
    fixed-size `(N, 3)` array aligned to the canonical schema point order
    (NaN for points that did not triangulate).
  * Appends a visibility column (1.0 if present, 0.0 if NaN).
  * Casts to the wire dtype (float32 by default — see the plan's "Open
    questions" decision: f32 on the wire is plenty for visualization and
    halves bandwidth vs the upstream f64).
  * Concatenates header + per-block (block_header + block_data) + footer into
    one contiguous bytearray ready for `websocket.send_bytes`.
"""
from __future__ import annotations

import logging

import numpy as np

from freemocap.api.websocket.binary_keypoints_protocol import (
    BLOCK_HEADER_SIZE,
    BlockKind,
    Dtype,
    KEYPOINTS_BLOCK_HEADER_DTYPE,
    KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE,
    MessageType,
    PAYLOAD_FOOTER_SIZE,
    PAYLOAD_HEADER_SIZE,
    TRACKER_ID_BYTES,
    CAMERA_ID_BYTES,
    numpy_dtype_for,
)

logger = logging.getLogger(__name__)


_WIRE_DTYPE: Dtype = Dtype.FLOAT32


def _densify_3d(
        sparse: dict[str, np.ndarray],
        point_names: tuple[str, ...] | list[str],
) -> np.ndarray:
    """Build an (N, 4) [x, y, z, visibility] array in canonical point-name order.

    Missing points → row of NaN with visibility 0.
    """
    n = len(point_names)
    arr = np.full((n, 4), np.nan, dtype=np.float32)
    arr[:, 3] = 0.0
    if not sparse:
        return arr
    for i, name in enumerate(point_names):
        coords = sparse.get(name)
        if coords is None:
            continue
        # Defensive: some upstream paths could hand us a (1, 3) or (3,)
        flat = np.asarray(coords, dtype=np.float32).reshape(-1)
        if flat.size < 3:
            continue
        arr[i, 0] = flat[0]
        arr[i, 1] = flat[1]
        arr[i, 2] = flat[2]
        arr[i, 3] = 1.0
    return arr


def _build_block(
        *,
        kind: BlockKind,
        tracker_id: str,
        point_names: tuple[str, ...] | list[str],
        sparse_arrays: dict[str, np.ndarray],
        camera_id: str = "",
) -> bytes:
    dims = 3
    interleaved = _densify_3d(sparse_arrays, point_names)
    wire_np_dtype = numpy_dtype_for(_WIRE_DTYPE)
    payload_arr = interleaved.astype(wire_np_dtype, copy=False)
    payload_bytes = payload_arr.tobytes(order="C")

    header = np.zeros(1, dtype=KEYPOINTS_BLOCK_HEADER_DTYPE)
    header["message_type"] = int(MessageType.KEYPOINTS_BLOCK_HEADER)
    header["block_kind"] = int(kind)
    header["dtype_code"] = int(_WIRE_DTYPE)
    header["dims"] = dims
    header["camera_id"] = camera_id.encode("ascii", errors="ignore")[:CAMERA_ID_BYTES]
    header["tracker_id"] = tracker_id.encode("ascii", errors="ignore")[:TRACKER_ID_BYTES]
    header["num_points"] = len(point_names)
    header["data_byte_length"] = len(payload_bytes)
    return header.tobytes() + payload_bytes


def build_keypoints_payload(
        *,
        frame_number: int,
        tracker_id: str,
        point_names: tuple[str, ...] | list[str],
        keypoints_raw_arrays: dict[str, np.ndarray],
        keypoints_filtered_arrays: dict[str, np.ndarray],
) -> bytearray:
    """Serialize the per-frame 3D keypoints into the binary wire format.

    Step 1 of the JSON→binary refactor: only `KEYPOINTS_RAW_3D` and
    `KEYPOINTS_FILTERED_3D` blocks. 2D overlays remain on the JSON path until
    Step 2.
    """
    blocks: list[bytes] = []
    blocks.append(
        _build_block(
            kind=BlockKind.KEYPOINTS_RAW_3D,
            tracker_id=tracker_id,
            point_names=point_names,
            sparse_arrays=keypoints_raw_arrays,
        )
    )
    blocks.append(
        _build_block(
            kind=BlockKind.KEYPOINTS_FILTERED_3D,
            tracker_id=tracker_id,
            point_names=point_names,
            sparse_arrays=keypoints_filtered_arrays,
        )
    )
    num_blocks = len(blocks)

    header = np.zeros(1, dtype=KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE)
    header["message_type"] = int(MessageType.KEYPOINTS_PAYLOAD_HEADER)
    header["frame_number"] = int(frame_number)
    header["num_blocks"] = num_blocks

    footer = np.zeros(1, dtype=KEYPOINTS_PAYLOAD_HEADER_FOOTER_DTYPE)
    footer["message_type"] = int(MessageType.KEYPOINTS_PAYLOAD_FOOTER)
    footer["frame_number"] = int(frame_number)
    footer["num_blocks"] = num_blocks

    total_size = (
        PAYLOAD_HEADER_SIZE
        + sum(len(b) for b in blocks)
        + PAYLOAD_FOOTER_SIZE
    )
    out = bytearray(total_size)
    offset = 0
    header_bytes = header.tobytes()
    out[offset:offset + len(header_bytes)] = header_bytes
    offset += len(header_bytes)
    for b in blocks:
        out[offset:offset + len(b)] = b
        offset += len(b)
    footer_bytes = footer.tobytes()
    out[offset:offset + len(footer_bytes)] = footer_bytes
    offset += len(footer_bytes)
    assert offset == total_size, (offset, total_size)
    return out
