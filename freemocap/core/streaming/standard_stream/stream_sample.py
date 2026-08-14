"""The standard-stream ``stream_sample`` binary wire format + codec.

One per frame: ``SAMPLE_HEADER`` + N blocks + ``SAMPLE_FOOTER``, contiguous,
little-endian, ``float32``. Names live in the schema, not here (no ``embed_names``).
Replaces the retired legacy keypoints protocol (D36).

Layout (numpy structured dtypes, ``align=True`` — sizes are locked by a test so the
frontend decoder stays in sync)::

    SAMPLE_HEADER   message_type u1 · timestamp f8 · frame_number i8 · subject_id u4 · num_blocks u4
    per block:      BLOCK_HEADER (message_type u1 · block_kind u1 · dtype_code u1 · cols u1 ·
                    camera_id S16 · overlay_layer u1 · num_elements u4 · data_byte_length u4)
                    + BLOCK_DATA (row-major f32)
    SAMPLE_FOOTER   mirrors SAMPLE_HEADER (integrity check)

Missing keypoints/segments → NaN rows. See
`current-work-plans/03-transport/standard-stream-protocol.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

import numpy as np


from freemocap.core.streaming.standard_stream.stream_schema import (
    ChannelKind,
    OverlayLayer,
    StreamSchema,
)

# Imported at runtime (not TYPE_CHECKING-only): beartype resolves these type
# annotations from the module namespace when ``from_aggregator_output`` /
# ``_camera_2d_detections`` / ``_origin_landmark_names`` are called, and a
# lazy forward-ref that cannot be imported would raise at the first call.
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage  # noqa: TC001 — resolved at runtime by beartype
from skellyforge.skellymodels.standard_human.standard_human_model import StandardHuman  # noqa: TC002 — resolved at runtime by beartype


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
        ("overlay_layer", "<u1"),
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

    ``camera_id`` and ``overlay_layer`` are set only for ``OVERLAY_2D`` blocks
    (one block per camera per layer).
    """

    kind: ChannelKind
    data: np.ndarray  # (num_elements, cols) — cast to float32 on encode
    camera_id: str = ""
    overlay_layer: OverlayLayer = OverlayLayer.DETECTIONS


@dataclass(slots=True)
class StreamSample:
    """One frame: a timestamp (primary key), ids, and the ordered blocks."""

    timestamp: float
    frame_number: int
    subject_id: int
    blocks: list[SampleBlock] = field(default_factory=list)

    # ── Encoder (aggregator output → six-group sample) ────────────────────
    # The frame source is the aggregator's output message; this method builds
    # the six blocks declared by the F1 schema. The schema is the SSOT for the
    # *names* (channel layout); the message carries the per-frame *numbers*.
    # See doc 11 §4 Step 1 + 09 § channels.

    @classmethod
    def from_aggregator_output(
        cls,
        *,
        message: AggregationNodeOutputMessage,
        schema: StreamSchema,
        standard_human: StandardHuman,
        timestamp: float | None = None,
        subject_id: int = 0,
    ) -> StreamSample:
        """Build one sample from one aggregator output message + the F1 schema.

        Fills the seven blocks in schema order:

        - **KEYPOINTS_3D** — the tracker-named measured keypoints; positions
          from ``message.keypoints_arrays`` (the filtered triangulations). NaN
          rows for missing; the 4th column (``reprojection_error``) is NaN
          (per-point reprojection error is wired with the per-camera overlay in
          F2b).
        - **LANDMARKS_3D** — the 76 hydrated standard-human landmarks;
          positions from ``message.standard_skeleton`` (the rigidified solver
          input). NaN rows for missing.
        - **SEGMENT_ORIGINS** — the 60 segments' ``origin_landmark`` positions
          from the same merged source; NaN for missing.
        - **ROTATIONS_LOCAL** / **ROTATIONS_WORLD** — 60 wxyz rows each, from
          the message's ``segment_rotations_local`` / ``segment_rotations_world``
          dicts; NaN rows for unsolved segments.
        - **DERIVED_POINTS** — ``center_of_mass`` + ``xcom`` (3-column rows).
          CoM from ``message.center_of_mass_result.total_body_com``; XCoM from
          ``message.xcom``. Both already computed by the aggregator (XCoM needs
          ``prev_com`` + ``dt`` state, which lives in the aggregator loop), so
          the encoder only *places* them; it never recomputes.
        - **OVERLAY_2D** — per camera × layer. The DETECTIONS layer is filled
          from the message's per-camera 2D detections (NaN-padded to the schema
          column count); the REPROJECTIONS layer stays NaN-allocated this task
          (its wiring is later — the fitted segment model projected back down).

        ``standard_human`` is required to resolve each segment's
        ``origin_landmark`` (the schema carries segment *names* only, not their
        origin keypoints).
        """
        groups = {g.kind: g for g in schema.channels}

        # The rigidified standard-human positions: merged body + standard-named
        # hands. ``standard_skeleton`` is the aggregator's exact solver input and
        # is keyed by standard-human names — the encoder cannot fall back to
        # tracker-named positions (``message.skeleton``) because those would be
        # silently fed into standard-human lookups as an all-NaN stream.
        positions: dict[str, np.ndarray] = message.standard_skeleton
        if not positions:
            raise ValueError(
                "from_aggregator_output: message.standard_skeleton is None/empty — "
                "the encoder requires the standard-human-keyed source; a message "
                "without it cannot produce a sample."
            )

        origin_names = cls._origin_landmark_names(standard_human)

        blocks: list[SampleBlock] = []

        # 0. KEYPOINTS_3D — the tracker-named measured keypoints
        # (``message.keypoints_arrays``); NaN rows where unobserved.
        kp_group = groups[ChannelKind.KEYPOINTS_3D]
        tracker_positions: dict[str, np.ndarray] = message.keypoints_arrays or {}
        blocks.append(
            SampleBlock(
                kind=ChannelKind.KEYPOINTS_3D,
                data=cls._assemble_rows(
                    names=kp_group.names,
                    positions=tracker_positions,
                    columns=kp_group.columns,
                ),
            )
        )

        # 1. LANDMARKS_3D — the 76 hydrated standard-human landmarks (the
        # rigidified solver input, ``message.standard_skeleton``); NaN rows
        # where unobserved.
        lm_group = groups[ChannelKind.LANDMARKS_3D]
        blocks.append(
            SampleBlock(
                kind=ChannelKind.LANDMARKS_3D,
                data=cls._assemble_rows(
                    names=lm_group.names,
                    positions=positions,
                    columns=lm_group.columns,
                ),
            )
        )

        # 2. SEGMENT_ORIGINS
        origin_positions = {
            segment_name: positions.get(origin_names[segment_name])
            for segment_name in groups[ChannelKind.SEGMENT_ORIGINS].names
        }
        blocks.append(
            SampleBlock(
                kind=ChannelKind.SEGMENT_ORIGINS,
                data=cls._assemble_rows(
                    names=groups[ChannelKind.SEGMENT_ORIGINS].names,
                    positions=origin_positions,
                    columns=groups[ChannelKind.SEGMENT_ORIGINS].columns,
                ),
            )
        )

        # 3/4. ROTATIONS_LOCAL / ROTATIONS_WORLD
        for kind, source in (
            (ChannelKind.ROTATIONS_LOCAL, message.segment_rotations_local),
            (ChannelKind.ROTATIONS_WORLD, message.segment_rotations_world),
        ):
            quats: dict[str, np.ndarray] = source or {}
            blocks.append(
                SampleBlock(
                    kind=kind,
                    data=cls._assemble_rows(
                        names=groups[kind].names,
                        positions=quats,
                        columns=groups[kind].columns,
                    ),
                )
            )

        # 5. DERIVED_POINTS
        com_row = np.full(3, np.nan)
        if message.center_of_mass_result is not None and not np.any(
            np.isnan(message.center_of_mass_result.total_body_com)
        ):
            com_row = message.center_of_mass_result.total_body_com.astype(np.float32)
        xcom_row = np.full(3, np.nan)
        if message.xcom is not None:
            xcom_row = np.array(
                [message.xcom.x, message.xcom.y, message.xcom.z], dtype=np.float32
            )
        derived_names = groups[ChannelKind.DERIVED_POINTS].names
        # Key each derived row by its schema-declared name (not by positional
        # tuple index) so a reordering of the schema's derived channels never
        # misplaces the CoM / XCoM rows.
        derived_by_name = {
            "center_of_mass": com_row,
            "xcom": xcom_row,
        }
        derived_data = np.stack([derived_by_name[n] for n in derived_names])
        blocks.append(
            SampleBlock(kind=ChannelKind.DERIVED_POINTS, data=derived_data.astype(np.float32))
        )

        # 6. OVERLAY_2D — one DETECTIONS block per camera this task.
        # DETECTIONS carry keypoint names (what the detector saw in that camera),
        # per 09 § 2D overlays. The REPROJECTIONS layer — the fitted segment model
        # projected back into each camera — is NOT emitted yet: the fitted model
        # is not projected down until the per-camera reprojection wiring (F2b).
        # The block-header ``overlay_layer`` byte now tags each block, so a
        # decoder can distinguish DETECTIONS (=0) from REPROJECTIONS (=1).
        kp_names = groups[ChannelKind.OVERLAY_2D].names
        for camera_id in schema.camera_ids:
            detections = cls._camera_2d_detections(message, camera_id)
            blocks.append(
                SampleBlock(
                    kind=ChannelKind.OVERLAY_2D,
                    data=cls._assemble_rows(
                        names=kp_names,
                        positions=detections,
                        columns=groups[ChannelKind.OVERLAY_2D].columns,
                    ),
                    camera_id=camera_id,
                    overlay_layer=OverlayLayer.DETECTIONS,
                )
            )

        return cls(
            timestamp=(
                float(timestamp) if timestamp is not None else 0.0
            ),
            frame_number=message.frame_number,
            subject_id=subject_id,
            blocks=blocks,
        )

    @staticmethod
    def _camera_2d_detections(
        message: AggregationNodeOutputMessage,
        camera_id: str,
    ) -> dict[str, np.ndarray]:
        """The per-camera tracker 2D detections (``name -> (x, y)``) for one camera.

        Reads the camera's ``skeleton_observation`` body-stage keypoints — the
        detector's raw 2D output for that camera's image. Missing/observable but
        NaN points are skipped (the encoder NaN-fills them). Returns an empty dict
        when there is no skeleton observation for this camera (2D-only mode).
        """
        cam_output = message.camera_node_outputs.get(camera_id)
        if cam_output is None or cam_output.skeleton_observation is None:
            return {}
        observation = cam_output.skeleton_observation
        body_stage = observation.stages.get("body")
        if body_stage is None or body_stage.keypoints is None:
            return {}
        kpts = body_stage.keypoints
        detections: dict[str, np.ndarray] = {}
        for i, name in enumerate(kpts.names):
            x, y, _z = kpts.xyz[i]
            if np.isnan(x) or np.isnan(y):
                continue
            detections[name] = np.array([x, y], dtype=np.float32)
        return detections

    @staticmethod
    def _origin_landmark_names(standard_human: StandardHuman) -> dict[str, str]:
        """segment name → origin keypoint name (from the canonical model)."""
        return {segment.name: segment.origin_landmark for segment in standard_human.segments}

    @staticmethod
    def _assemble_rows(
        *,
        names: tuple[str, ...],
        positions: dict[str, np.ndarray | None],
        columns: tuple[str, ...],
    ) -> np.ndarray:
        """Build a ``(len(names), len(columns))`` float32 block: each name's
        position (first ``len(columns)`` coords) if present, else a NaN row.

        ``columns`` is the group's per-element column tuple (e.g. ``("x","y","z")``
        for a point group, ``("x","y","z","reprojection_error")`` for KEYPOINTS_3D,
        ``("x","y","visibility")`` for OVERLAY_2D). A position vector may carry more
        or fewer values than the group declares; the first ``len(columns)`` coords
        are placed, the remainder (e.g. reprojection_error / visibility) NaN-filled,
        and a shorter vector is NaN-padded.
        """
        n_cols = len(columns)
        rows = np.full((len(names), n_cols), np.nan, dtype=np.float32)
        for i, name in enumerate(names):
            pos = positions.get(name)
            if pos is None:
                continue
            arr = np.asarray(pos, dtype=np.float32)
            if arr.size == 0:
                continue
            k = min(n_cols, int(arr.size))
            rows[i, :k] = arr[:k]
        return rows

    # ── Codec (six-group binary) ─────────────────────────────────────────
    # All numpy on the wire, float32 (== the original codec's ``_WIRE_DTYPE``);
    # see the protocol doc 09 § stream_sample. The schema carries the channel
    # metadata (block kinds, column counts) needed to decode names.

    def to_bytes(self) -> bytes:
        """Serialize this sample to the binary wire format."""
        return encode_sample(self)

    @classmethod
    def from_bytes(cls, buf: bytes) -> StreamSample:
        """Reconstruct a sample from the binary wire format."""
        return decode_sample(buf)


def encode_sample(sample: StreamSample) -> bytes:
    """Serialize one sample to the binary wire format.

    Header/footer buffers are zeroed from a flat ``bytearray`` before the fields
    are written — ``np.zeros`` on an ``align=True`` structured dtype does *not*
    reliably zero the alignment padding (it can leave garbage bytes, breaking
    the deterministic-encode contract the golden-byte parity tests rely on).
    """
    header = np.frombuffer(bytearray(SAMPLE_HEADER_SIZE), dtype=SAMPLE_HEADER_DTYPE, count=1)
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

        block_header = np.frombuffer(bytearray(BLOCK_HEADER_SIZE), dtype=BLOCK_HEADER_DTYPE, count=1)
        block_header["message_type"] = int(MessageType.BLOCK_HEADER)
        block_header["block_kind"] = int(block.kind)
        block_header["dtype_code"] = int(DtypeCode.FLOAT32)
        block_header["cols"] = cols
        block_header["camera_id"] = block.camera_id.encode("ascii", errors="ignore")[:CAMERA_ID_BYTES]
        block_header["overlay_layer"] = int(block.overlay_layer)
        block_header["num_elements"] = num_elements
        block_header["data_byte_length"] = len(data_bytes)

        parts.append(block_header.tobytes())
        parts.append(data_bytes)

    footer = np.frombuffer(bytearray(SAMPLE_HEADER_SIZE), dtype=SAMPLE_HEADER_DTYPE, count=1)
    footer["message_type"] = int(MessageType.SAMPLE_FOOTER)
    footer["timestamp"] = sample.timestamp
    footer["frame_number"] = sample.frame_number
    footer["subject_id"] = sample.subject_id
    footer["num_blocks"] = len(sample.blocks)
    parts.append(footer.tobytes())
    return b"".join(parts)


def decode_sample(buf: bytes) -> StreamSample:
    """Reconstruct one sample from the binary wire format.

    Blocks are self-describing (kind / cols / num_elements / camera_id); mapping a
    block's columns back to keypoint names is the schema's job, not the sample's.
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
            SampleBlock(
                kind=ChannelKind(int(block_header["block_kind"])),
                data=data.copy(),
                camera_id=camera_id,
                overlay_layer=OverlayLayer(int(block_header["overlay_layer"])),
            )
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
