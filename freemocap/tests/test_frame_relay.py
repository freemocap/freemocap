"""F2b — FrameRelay integration (schema-then-samples + ack-window gating).

Drives the real FrameRelay through a controllable source queue and a fake
WebSocket. Verifies the supervisor's contract: the schema JSON is sent first
(on connect), then binary sample frames flow as aggregator output arrives —
gated by the ack window.
"""
import asyncio

import numpy as np
from starlette.websockets import WebSocketState

from freemocap.api.websocket.backpressure_controller import BackpressureController
from freemocap.api.websocket.frame_relay import FrameRelay, lengths_differ_materially, schema_bytes
from freemocap.api.websocket.send_serializer import SendSerializer
from freemocap.core.streaming.standard_stream import (
    MessageType,
    StreamSchema,
    decode_sample,
)
from freemocap.core.tasks.mocap.center_of_mass import CoMConfidence, CenterOfMassResult
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage
from skellyforge.data_models.trajectory_3d import Point3d
from skellyforge.skellymodels.standard_human.standard_human_model import compose_standard_human


class FakeWebSocket:
    def __init__(self):
        self.client_state = WebSocketState.CONNECTED
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.client_state = WebSocketState.DISCONNECTED


def _model():
    return compose_standard_human()


def _schema():
    return StreamSchema.from_standard_human(
        stream_id="relay-test",
        stream_name="relay-test",
        standard_human=_model(),
        camera_ids=("cam-0",),
    )


async def _wait_for_sent_bytes(ws: FakeWebSocket, count: int, timeout: float = 5.0) -> None:
    """Poll until the relay has written ``count`` byte frames, or timeout."""
    import time

    deadline = time.monotonic() + timeout
    while len(ws.sent_bytes) < count:
        if time.monotonic() >= deadline:
            raise AssertionError(
                f"Timed out waiting for {count} sent_bytes (got {len(ws.sent_bytes)})"
            )
        await asyncio.sleep(0.001)


def _message(frame_number: int) -> AggregationNodeOutputMessage:
    return AggregationNodeOutputMessage(
        frame_number=frame_number,
        pipeline_config=RealtimePipelineConfig(),
        camera_group_id="cg-0",
        camera_node_outputs={},
        center_of_mass_result=CenterOfMassResult(
            total_body_com=np.array([0.0, 0.0, 900.0]),
            segment_coms={},
            directly_observed_mass=1.0,
            confidence=CoMConfidence.high,
        ),
        xcom=Point3d(x=1.0, y=0.0, z=0.0),
        standard_skeleton={"hips_center": np.array([0.0, 0.0, 900.0])},
        segment_rotations_world={},
        segment_rotations_local={},
    )


async def test_schema_sent_before_samples_and_ack_gates_window():
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    backpressure = BackpressureController(window_size=2, reset_threshold=300)
    schema = _schema()

    # The source pushes the same frame until told to yield None (empty tick).
    queue: asyncio.Queue[AggregationNodeOutputMessage | None] = asyncio.Queue()

    async def source():
        return await queue.get()

    relay = FrameRelay(
        serializer=serializer,
        backpressure=backpressure,
        schema=schema,
        standard_human=_model(),
        source=source,
    )

    # 1. Supervisor contract: schema first (on connect), before any sample.
    await serializer.send_schema_json(schema_bytes(schema))
    assert len(ws.sent_text) == 1
    assert ws.sent_text[0].startswith("{")
    assert '"stream_schema"' in ws.sent_text[0]
    assert ws.sent_bytes == []

    # 2. Start the relay and feed frames.
    relay_task = asyncio.create_task(relay.run())

    # Feed frame 0 and 1 (window=2); a third would WAIT but we don't feed it yet.
    await queue.put(_message(0))
    await queue.put(_message(1))
    # Wait until the loop has consumed both (poll, not a fixed sleep).
    await _wait_for_sent_bytes(ws, 2)

    # Ack frame 0 → frees a slot; now the relay can send frame 2.
    relay.ack(0)
    await queue.put(_message(2))
    await _wait_for_sent_bytes(ws, 3)

    relay_task.cancel()
    try:
        await relay_task
    except asyncio.CancelledError:
        pass

    # All three frames became binary sample frames with the sample tag byte.
    assert len(ws.sent_bytes) >= 1
    assert ws.sent_bytes[0][0] == int(MessageType.SAMPLE_HEADER)
    for blob in ws.sent_bytes:
        sample = decode_sample(blob)
        assert sample.frame_number in (0, 1, 2)
        # six groups → 5 non-overlay + 1 overlay(cam-0) = 6 blocks
        assert len(sample.blocks) == 6

    # Backpressure recomputed after acks/sends: last_sent is the max observed.
    assert backpressure.last_sent == 2


# ── Material-change predicate ─────────────────────────────────────────────


def test_lengths_differ_materially_first_arrival_fires():
    assert lengths_differ_materially(None, {"hips": 246.5}) is True


def test_lengths_differ_materially_below_threshold_no_fire():
    old = {"hips": 246.5}
    assert lengths_differ_materially(old, {"hips": 247.0}) is False  # 0.5 mm < 1.0
    assert lengths_differ_materially(old, {"hips": 246.5}) is False  # unchanged


def test_lengths_differ_materially_above_threshold_fires():
    old = {"hips": 246.5}
    assert lengths_differ_materially(old, {"hips": 247.6}) is True  # 1.1 mm > 1.0


def test_lengths_differ_materially_new_segment_fires():
    old = {"hips": 246.5}
    assert lengths_differ_materially(old, {"hips": 246.5, "spine": 263.5}) is True


def test_message_carries_segment_lengths():
    """The aggregator output message carries the rigidifier's measured lengths."""
    synthetic = {
        "hips": 246.5,
        "left_upper_arm": 333.0,
        "right_hand": 180.0,
        "left_thumb_distal": 25.0,
    }
    msg = AggregationNodeOutputMessage(segment_lengths=synthetic)
    assert msg.segment_lengths == synthetic


def test_message_defaults_segment_lengths_empty():
    msg = AggregationNodeOutputMessage()
    assert msg.segment_lengths == {}
