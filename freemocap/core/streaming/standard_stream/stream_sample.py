"""The standard-stream ``stream_sample`` binary wire format + codec.

One per frame: ``SAMPLE_HEADER`` + N blocks + ``SAMPLE_FOOTER``, contiguous,
little-endian, ``float32``. Names live in the schema, not here (no ``embed_names``).
Evolves ``freemocap/api/websocket/binary_keypoints_protocol.py``.

Layout (numpy structured dtypes, ``align=True`` — sizes are locked by a test so the
frontend decoder stays in sync)::

    SAMPLE_HEADER   message_type u1 · timestamp f8 · frame_number i8 · subject_id u4 · num_blocks u4
    per block:      BLOCK_HEADER (message_type u1 · block_kind u1 · dtype_code u1 · cols u1 ·
                    camera_id S16 · num_elements u4 · data_byte_length u4) + BLOCK_DATA (row-major f32)
    SAMPLE_FOOTER   mirrors SAMPLE_HEADER (integrity check)

Missing landmarks/segments → NaN rows. See
[09 — Standard Stream Protocol](docs/streaming-compatibility/09-standard-stream-protocol.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

import numpy as np

from freemocap.core.streaming.standard_stream.stream_schema import ChannelKind


class MessageType(IntEnum):
    """First-byte tags. Distinct from skellycam's image protocol (0/1/2) and the
    legacy keypoints protocol (3/4/5) so a receiver can demux on byte 0."""

    SAMPLE_HEADER = 10
    BLOCK_HEADER = 11
    SAMPLE_FOOTER = 12


class DtypeCode(IntEnum):
    FLOAT32 = 0


CAMERA_ID_BYTES = 16
_WIRE_DTYPE = np.dtype("<f4")  # float32 on the wire


SAMPLE_HEADER_DTYPE = np.dtype(
    [
        ("message_type", "<u1"),
        ("timestamp", "<f8"),
        ("frame_number", "<i8"),
        ("subject_id", "<u4"),
        ("num_blocks", "<u4"),
    ],
    align=True,
)

BLOCK_HEADER_DTYPE = np.dtype(
    [
        ("message_type", "<u1"),
        ("block_kind", "<u1"),
        ("dtype_code", "<u1"),
        ("cols", "<u1"),
        ("camera_id", f"S{CAMERA_ID_BYTES}"),
        ("num_elements", "<u4"),
        ("data_byte_length", "<u4"),
    ],
    align=True,
)

SAMPLE_HEADER_SIZE = SAMPLE_HEADER_DTYPE.itemsize
BLOCK_HEADER_SIZE = BLOCK_HEADER_DTYPE.itemsize
SAMPLE_FOOTER_SIZE = SAMPLE_HEADER_DTYPE.itemsize  # footer mirrors header


@dataclass(slots=True)
class SampleBlock:
    """One block of a sample: a (num_elements, cols) float array of one kind.

    ``camera_id`` is set only for ``OVERLAY_2D`` blocks (one block per camera).
    """

    kind: ChannelKind
    data: np.ndarray  # (num_elements, cols) — cast to float32 on encode
    camera_id: str = ""


@dataclass(slots=True)
class StreamSample:
    """One frame: a timestamp (primary key), ids, and the ordered blocks."""

    timestamp: float
    frame_number: int
    subject_id: int
    blocks: list[SampleBlock] = field(default_factory=list)


def encode_sample(sample: StreamSample) -> bytes:
    """Serialize one sample to the binary wire format."""
    header = np.zeros(1, dtype=SAMPLE_HEADER_DTYPE)
    header["message_type"] = int(MessageType.SAMPLE_HEADER)
    header["timestamp"] = sample.timestamp
    header["frame_number"] = sample.frame_number
    header["subject_id"] = sample.subject_id
    header["num_blocks"] = len(sample.blocks)

    parts: list[bytes] = [header.tobytes()]
    for block in sample.blocks:
        arr = np.ascontiguousarray(block.data, dtype=_WIRE_DTYPE)
        if arr.ndim != 2:
            raise ValueError(f"block data must be 2D (num_elements, cols), got shape {arr.shape}")
        num_elements, cols = arr.shape
        data_bytes = arr.tobytes(order="C")

        block_header = np.zeros(1, dtype=BLOCK_HEADER_DTYPE)
        block_header["message_type"] = int(MessageType.BLOCK_HEADER)
        block_header["block_kind"] = int(block.kind)
        block_header["dtype_code"] = int(DtypeCode.FLOAT32)
        block_header["cols"] = cols
        block_header["camera_id"] = block.camera_id.encode("ascii", errors="ignore")[:CAMERA_ID_BYTES]
        block_header["num_elements"] = num_elements
        block_header["data_byte_length"] = len(data_bytes)

        parts.append(block_header.tobytes())
        parts.append(data_bytes)

    footer = header.copy()
    footer["message_type"] = int(MessageType.SAMPLE_FOOTER)
    parts.append(footer.tobytes())
    return b"".join(parts)


def decode_sample(buf: bytes) -> StreamSample:
    """Reconstruct one sample from the binary wire format.

    Blocks are self-describing (kind / cols / num_elements / camera_id); mapping a
    block's columns back to landmark names is the schema's job, not the sample's.
    """
    view = memoryview(buf)
    header = np.frombuffer(view[:SAMPLE_HEADER_SIZE], dtype=SAMPLE_HEADER_DTYPE)[0]
    if int(header["message_type"]) != int(MessageType.SAMPLE_HEADER):
        raise ValueError("standard-stream sample: bad SAMPLE_HEADER message_type")
    num_blocks = int(header["num_blocks"])

    cursor = SAMPLE_HEADER_SIZE
    blocks: list[SampleBlock] = []
    for _ in range(num_blocks):
        block_header = np.frombuffer(view[cursor:cursor + BLOCK_HEADER_SIZE], dtype=BLOCK_HEADER_DTYPE)[0]
        if int(block_header["message_type"]) != int(MessageType.BLOCK_HEADER):
            raise ValueError("standard-stream sample: bad BLOCK_HEADER message_type")
        cursor += BLOCK_HEADER_SIZE

        cols = int(block_header["cols"])
        num_elements = int(block_header["num_elements"])
        data_len = int(block_header["data_byte_length"])
        data = np.frombuffer(view[cursor:cursor + data_len], dtype=_WIRE_DTYPE).reshape(num_elements, cols)
        cursor += data_len

        camera_id = bytes(block_header["camera_id"]).decode("ascii", errors="ignore").rstrip("\x00")
        blocks.append(
            SampleBlock(kind=ChannelKind(int(block_header["block_kind"])), data=data.copy(), camera_id=camera_id)
        )

    footer = np.frombuffer(view[cursor:cursor + SAMPLE_FOOTER_SIZE], dtype=SAMPLE_HEADER_DTYPE)[0]
    if int(footer["message_type"]) != int(MessageType.SAMPLE_FOOTER):
        raise ValueError("standard-stream sample: bad SAMPLE_FOOTER message_type")
    if int(footer["num_blocks"]) != num_blocks:
        raise ValueError("standard-stream sample: footer/header num_blocks mismatch")
    cursor += SAMPLE_FOOTER_SIZE
    if cursor != len(buf):
        raise ValueError(f"standard-stream sample: trailing bytes ({cursor} of {len(buf)} consumed)")

    return StreamSample(
        timestamp=float(header["timestamp"]),
        frame_number=int(header["frame_number"]),
        subject_id=int(header["subject_id"]),
        blocks=blocks,
    )
