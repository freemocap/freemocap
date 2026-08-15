"""F2b — FrameRelay integration (schema-then-samples, newest-wins).

Drives the real FrameRelay through a controllable FrameContext source and a
fake WebSocket. Verifies the supervisor's contract: the schema JSON is sent
first (on connect), then binary sample frames flow as frame contexts arrive —
composed through the channel producers. There is no ack window: the relay
sends every context the source yields (newest-wins lives in the source).
"""
import asyncio

import numpy as np
from starlette.websockets import WebSocketState

from freemocap.api.websocket.frame_relay import FrameRelay
from freemocap.api.websocket.send_serializer import SendSerializer
from freemocap.core.streaming.standard_stream import (
    MessageType,
    decode_sample,
    encode_schema,
)
from freemocap.core.streaming.standard_stream.producers import compose
from freemocap.core.streaming.standard_stream.producers.producer_contexts import (
    FrameContext,
    StreamContext,
)
from freemocap.core.tasks.mocap.center_of_mass import CoMConfidence, CenterOfMassResult
from freemocap.core.tasks.mocap.tracker_mappings import tracker_keypoint_names
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


def _composition():
    return compose(
        StreamContext(
            standard_human=_model(),
            camera_ids=("cam-0",),
            tracker_keypoint_names=tracker_keypoint_names("rtmpose"),
            pipeline_live=True,
        ),
        stream_id="relay-test",
        stream_name="relay-test",
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


def _frame_ctx(frame_number: int) -> FrameContext:
    return FrameContext(
        frame_number=frame_number,
        timestamp=0.0,
        aggregator_output=_message(frame_number),
        image_payload=b"jpeg",
    )


async def test_schema_sent_before_samples_and_frames_relay():
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    composition = _composition()

    queue: asyncio.Queue[FrameContext | None] = asyncio.Queue()

    async def source():
        return await queue.get()

    relay = FrameRelay(
        serializer=serializer,
        source=source,
        should_continue=lambda: True,
    )
    relay.set_composition(composition)

    # 1. Supervisor contract: schema first (on connect), before any sample.
    await serializer.send_schema_json(encode_schema(composition.schema))
    assert len(ws.sent_text) == 1
    assert ws.sent_text[0].startswith("{")
    assert '"stream_schema"' in ws.sent_text[0]
    assert ws.sent_bytes == []

    # 2. Start the relay and feed frames — every context becomes one sample
    # (no ack window gates the send).
    relay_task = asyncio.create_task(relay.run())

    await queue.put(_frame_ctx(0))
    await queue.put(_frame_ctx(1))
    await _wait_for_sent_bytes(ws, 2)

    await queue.put(_frame_ctx(2))
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

    assert relay.last_sent_frame_number == 2


async def test_relay_stops_on_its_own_when_should_continue_flips():
    """A2 — the relay owns its exit condition; no reliance on task cancel."""
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    queue: asyncio.Queue[FrameContext | None] = asyncio.Queue()

    async def source():
        return await queue.get()

    keep_running = {"value": True}
    relay = FrameRelay(
        serializer=serializer,
        source=source,
        should_continue=lambda: keep_running["value"],
    )
    relay.set_composition(_composition())

    task = asyncio.create_task(relay.run())
    await asyncio.sleep(0.05)
    assert not task.done()  # running, blocked on the empty source

    keep_running["value"] = False
    await queue.put(None)  # wake it so it can observe the flag
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done()
    assert not task.cancelled()  # exited by its own loop condition, not a cancel


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
