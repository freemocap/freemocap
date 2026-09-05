"""FrameRelay integration (self-describing message path, newest-wins).

Drives the real FrameRelay through a controllable FrameContext source and a
fake WebSocket. Verifies the relay's contract: each frame context composes into
one self-describing CBOR frame message and is sent. There is no ack window —
the relay sends every context the source yields (newest-wins lives in the
source).
"""
import asyncio
import time

import cbor2
import numpy as np
from starlette.websockets import WebSocketState

from freemocap.api.websocket.frame_relay import FrameRelay
from freemocap.api.websocket.send_serializer import SendSerializer
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
from freemocap.core.skeletons.standard_human_skeleton import (
    STANDARD_HUMAN_MODEL_ID,
    build_standard_human_bundle,
)
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage
from skellyforge.core.skeleton.skeleton_definition import SkeletonDefinition


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


def _human_bundle():
    return build_standard_human_bundle(detector_type="rtmpose")


def _composition():
    return compose_messages(
        StreamContext(
            skeletons=(_human_bundle(),),
            camera_ids=("cam-0",),
            pipeline_live=True,
        )
    )


async def _wait_for_sent_bytes(ws: FakeWebSocket, count: int, timeout: float = 5.0) -> None:
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
        reconstructions={
            STANDARD_HUMAN_MODEL_ID: SkeletonReconstruction(
                model_id=STANDARD_HUMAN_MODEL_ID,
                landmarks={"pelvis_origin": np.array([0.0, 0.0, 900.0])},
                center_of_mass=np.array([0.0, 0.0, 900.0]),
                extrapolated_center_of_mass=np.array([1.0, 0.0, 0.0]),
            )
        },
    )


def _frame_ctx(frame_number: int) -> FrameContext:
    return FrameContext(
        frame_number=frame_number,
        timestamp=0.0,
        aggregator_output=_message(frame_number),
        image_payload=b"jpeg",
    )


async def test_frames_relay_as_cbor_messages():
    ws = FakeWebSocket()
    serializer = SendSerializer(ws)
    queue: asyncio.Queue[FrameContext | None] = asyncio.Queue()

    async def source():
        return await queue.get()

    relay = FrameRelay(serializer=serializer, source=source, should_continue=lambda: True)
    relay.set_composition(_composition())

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

    frame_numbers = []
    for blob in ws.sent_bytes:
        message = cbor2.loads(blob)
        assert message["kind"] == "frame"
        frame_numbers.append(message["frame_number"])
    assert frame_numbers == [0, 1, 2]
    assert relay.last_sent_frame_number == 2


async def test_relay_stops_on_its_own_when_should_continue_flips():
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
    assert not task.done()

    keep_running["value"] = False
    await queue.put(None)
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done()
    assert not task.cancelled()


def test_message_carries_a_reconstruction_per_skeleton():
    """The message is keyed by model: a session tracking two things publishes two."""
    synthetic = {"hips": 246.5, "left_upper_arm": 333.0}
    msg = AggregationNodeOutputMessage(
        reconstructions={
            "standard_human": SkeletonReconstruction(
                model_id="standard_human", segment_lengths=synthetic, fitted_scale_mm=1700.0
            ),
            "charuco_board": SkeletonReconstruction(
                model_id="charuco_board", fitted_scale_mm=54.0
            ),
        }
    )
    assert msg.reconstructions["standard_human"].segment_lengths == synthetic
    assert msg.reconstructions["charuco_board"].fitted_scale_mm == 54.0


def test_message_defaults_to_no_reconstructions():
    """A frame where nothing hydrated carries none — not an empty human."""
    assert AggregationNodeOutputMessage().reconstructions == {}
