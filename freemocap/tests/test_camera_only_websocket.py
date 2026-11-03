"""Camera-only frame polling uses SkellyCam's group-local cursor contract."""

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from threading import Condition
from threading import Event
from queue import Queue
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
import pytest
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from starlette.websockets import WebSocket

from freemocap.api.websocket import websocket_server
from freemocap.api.websocket.websocket_server import WebsocketServer
from freemocap.app.freemocap_application import FreemocapApplication
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.startup_status import RealtimeStartupStatus
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.producers.producer_contexts import StreamContext


@dataclass
class CameraPayload:
    id: str
    frame_number: int

    def get_latest_frontend_payload(
        self,
        *,
        if_newer_than: int,
        display_image_sizes: dict[str, dict[str, float]] | None,
    ) -> tuple[int, float, memoryview] | None:
        if self.frame_number <= if_newer_than:
            return None
        return self.frame_number, float(self.frame_number), memoryview(b"image")


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> WebsocketServer:
    manager = CameraGroupManager.__new__(CameraGroupManager)
    manager.closing = False
    manager.camera_groups = {}
    app = FreemocapApplication.__new__(FreemocapApplication)
    app.camera_group_manager = manager
    app.startup_status = RealtimeStartupStatus()
    app.inference_service = SimpleNamespace(has_result=Mock(return_value=True))
    monkeypatch.setattr(websocket_server, "get_freemocap_app", lambda: app)
    monkeypatch.setattr(
        WebsocketServer,
        "_compose_current",
        lambda self: compose_messages(StreamContext(skeletons=())),
    )
    fastapi = FastAPI()
    fastapi.state.log_relay = Mock()
    fastapi.state.global_kill_flag = SimpleNamespace(value=False)
    result = WebsocketServer(
        fastapi_app=fastapi,
        websocket=WebSocket(
            scope={"type": "websocket", "query_string": b"connection_id=test"}, receive=AsyncMock(), send=AsyncMock()
        ),
    )
    monkeypatch.setattr(result, "_ensure_composition", AsyncMock())
    monkeypatch.setattr(result, "_record_framerate", Mock())
    monkeypatch.setattr(result, "_send_framerate_updates", AsyncMock())
    return result


async def test_empty_manager_accepts_initial_cursor(server: WebsocketServer) -> None:
    assert await server._await_camera_only_frame() is None
    assert server._camera_frame_cursors == {}


async def test_stopped_pipeline_does_not_block_reconnected_camera_video(server: WebsocketServer) -> None:
    server._app.realtime_pipeline_manager = SimpleNamespace(
        pipelines={"stopped": SimpleNamespace(alive=False)},
    )
    server._app.camera_group_manager.camera_groups = {
        "replacement": CameraPayload(id="replacement", frame_number=12),
    }
    server._app.get_latest_aggregator_outputs = Mock(return_value=[])
    server._app.wait_for_realtime_result = AsyncMock()
    frame = await server._await_next_frame()
    assert frame is not None and frame.frame_number == 12
    server._app.wait_for_realtime_result.assert_not_awaited()


async def test_live_pipeline_still_waits_for_matching_reconstruction(server: WebsocketServer) -> None:
    server._pipeline_source_ids = ("live",)
    server._pipeline_frame_cursor = 1
    server._preview_mode = False
    server._last_processed_frame_at = websocket_server.time.perf_counter()
    server._app.realtime_pipeline_manager = SimpleNamespace(
        pipelines={"live": SimpleNamespace(alive=True, config=RealtimePipelineConfig())},
    )
    server._app.camera_group_manager.camera_groups = {
        "capture": CameraPayload(id="capture", frame_number=12),
    }
    server._app.get_latest_aggregator_outputs = Mock(return_value=[])
    server._app.wait_for_realtime_result = AsyncMock()
    frame = await server._await_next_frame()
    assert frame is None
    assert not server._preview_mode
    server._app.wait_for_realtime_result.assert_awaited_once()


async def test_processing_cursor_is_independent_of_capture_cursor(server: WebsocketServer) -> None:
    server._relay._last_sent_frame_number = 10000
    server._pipeline_source_ids = ("old",)
    server._pipeline_frame_cursor = 500
    server._app.realtime_pipeline_manager = SimpleNamespace(
        pipelines={"new": SimpleNamespace(alive=True, config=RealtimePipelineConfig())},
    )
    server._app.get_latest_aggregator_outputs = Mock(return_value=[])
    server._app.wait_for_realtime_result = AsyncMock()
    assert await server._await_next_frame() is None
    assert [call.kwargs["if_newer_than"] for call in server._app.get_latest_aggregator_outputs.call_args_list] == [-1]
    server._app.wait_for_realtime_result.assert_not_awaited()


@pytest.mark.parametrize("fails", [False, True])
async def test_connection_exit_joins_tasks_without_stopping_app(
    server: WebsocketServer, monkeypatch: pytest.MonkeyPatch, fails: bool,
) -> None:
    async def idle() -> None:
        await asyncio.Event().wait()

    async def finish() -> None:
        if fails:
            raise ValueError("frame delivery failed")

    monkeypatch.setattr(server._relay, "run", idle)
    for name in ("_logs_relay", "_app_state_sender", "_posthoc_progress_sender"):
        monkeypatch.setattr(server, name, idle)
    monkeypatch.setattr(server, "_client_message_handler", finish)
    if fails:
        with pytest.raises(ValueError, match="frame delivery failed"):
            await server.run()
    else:
        await server.run()
    assert all(task.done() for task in server.ws_tasks)
    assert not server._global_kill_flag.value
    assert not server.should_continue


async def test_group_counters_are_independent(server: WebsocketServer) -> None:
    server._app.camera_group_manager.camera_groups = {
        "fast": CameraPayload(id="fast", frame_number=100),
        "slow": CameraPayload(id="slow", frame_number=2),
    }
    first = await server._await_camera_only_frame()
    assert first is not None and first.frame_number == 100
    second = await server._await_camera_only_frame()
    assert second is not None and second.frame_number == 2
    assert await server._await_camera_only_frame() is None
    server._app.camera_group_manager.camera_groups["slow"].frame_number = 3
    third = await server._await_camera_only_frame()
    assert third is not None and third.frame_number == 3


async def test_preview_during_model_loading_upgrades_to_matching_processed_frame(server: WebsocketServer,
                                                                               monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setattr(websocket_server, "time", SimpleNamespace(perf_counter=lambda: clock[0]))
    inference = InferenceService.__new__(InferenceService)
    inference._condition = Condition()
    inference._startup_records = {"live": {"phase": "loading_models"}}
    server._app.inference_service = inference
    camera = CameraPayload(id="capture", frame_number=100)
    server._app.camera_group_manager.camera_groups = {"capture": camera}
    capture = SimpleNamespace(get_frontend_payload_by_frame_number=Mock(return_value=(b"matched", 9.25)))
    pipeline = SimpleNamespace(alive=True, config=RealtimePipelineConfig(), camera_group=capture)
    server._app.realtime_pipeline_manager = SimpleNamespace(pipelines={"live": pipeline})
    output = Mock(spec=AggregationNodeOutputMessage, pipeline_id="live", camera_group_id="capture", frame_number=9,
                  pipeline_config=pipeline.config, camera_node_outputs={})
    server._app.get_latest_aggregator_outputs = Mock(return_value=[output])
    server._app.wait_for_realtime_result = AsyncMock()

    preview = await server._await_next_frame()
    assert preview.frame_number == 100 and preview.timestamp == 100.0
    assert preview.aggregator_output is None and bytes(preview.image_payload) == b"image"
    server._app.get_latest_aggregator_outputs.assert_not_called()
    capture.get_frontend_payload_by_frame_number.assert_not_called()
    server._app.wait_for_realtime_result.assert_not_awaited()
    server._ensure_composition.assert_awaited_with(None)

    inference._startup_records["live"]["phase"] = "running"
    # An older aggregator timeout is not proof that this frame has inference.
    camera.frame_number = 101
    timeout_preview = await server._await_next_frame()
    assert timeout_preview.aggregator_output is None and timeout_preview.frame_number == 101
    assert server._pipeline_frame_cursor == -1
    capture.get_frontend_payload_by_frame_number.assert_not_called()
    # Non-None includes a valid empty/no-person observation: visibility is not readiness.
    output.camera_node_outputs = {"camera": SimpleNamespace(skeleton_observation=SimpleNamespace(stages={}))}
    processed = await server._await_next_frame()
    assert processed.aggregator_output is output and processed.frame_number == 9
    assert processed.timestamp == 9.25 and processed.image_payload == b"matched"
    capture.get_frontend_payload_by_frame_number.assert_called_once_with(
        frame_number=9, display_image_sizes=server._display_image_sizes,
    )
    assert server._camera_frame_cursors == {"capture": 101}
    assert server._pipeline_frame_cursor == 9

    # A processing stall waits once, then continues preview at capture cadence.
    server._app.get_latest_aggregator_outputs.return_value = []
    camera.frame_number = 102
    clock[0] += 0.51
    stalled = await server._await_next_frame()
    assert stalled.frame_number == 102 and stalled.aggregator_output is None
    server._app.wait_for_realtime_result.assert_awaited_once_with(timeout=0.5)
    camera.frame_number = 103
    assert (await server._await_next_frame()).frame_number == 103
    assert server._app.wait_for_realtime_result.await_count == 1
    assert server._preview_mode

    output.frame_number = 10
    server._app.get_latest_aggregator_outputs.return_value = [output]
    resumed = await server._await_next_frame()
    assert resumed.frame_number == 10 and resumed.aggregator_output is output
    assert not server._preview_mode
    assert server._app.wait_for_realtime_result.await_count == 1

    # A subsequent inference failure must not expose the retained last result.
    inference._startup_records["live"]["phase"] = "failed"
    camera.frame_number = 104
    after_failure = await server._await_next_frame()
    assert after_failure.aggregator_output is None and after_failure.frame_number == 104
    assert capture.get_frontend_payload_by_frame_number.call_count == 2


@pytest.mark.parametrize("expired", [False, True])
async def test_missing_matched_image_preserves_startup_preview(server: WebsocketServer, expired: bool) -> None:
    capture = SimpleNamespace(get_frontend_payload_by_frame_number=Mock(
        side_effect=IndexError("expired") if expired else None, return_value=None,
    ))
    config = RealtimePipelineConfig()
    config.camera_node_config.skeleton_tracking_enabled = False
    server._app.realtime_pipeline_manager = SimpleNamespace(
        pipelines={"live": SimpleNamespace(alive=True, config=config, camera_group=capture)},
    )
    output = Mock(spec=AggregationNodeOutputMessage, pipeline_id="live", frame_number=1, pipeline_config=config)
    server._app.get_latest_aggregator_outputs = Mock(return_value=[output])
    server._app.wait_for_realtime_result = AsyncMock()
    server._app.camera_group_manager.camera_groups = {"capture": CameraPayload(id="capture", frame_number=10)}
    frame = await server._await_next_frame()
    assert frame.frame_number == 10 and frame.aggregator_output is None
    assert server._preview_mode and server._pipeline_frame_cursor == 1
    server._app.wait_for_realtime_result.assert_not_awaited()


@pytest.mark.parametrize("terminal", ["failed", "stopping", "stopped"])
async def test_failed_or_cancelled_processing_preserves_raw_preview(server: WebsocketServer, terminal: str) -> None:
    server._app.startup_status.begin()
    server._app.startup_status.pipeline_created("live")
    if terminal == "failed":
        server._app.startup_status.fail("model failed")
    else:
        server._app.startup_status.request_stop()
        if terminal == "stopped":
            server._app.startup_status.stopped()
    server._app.realtime_pipeline_manager = SimpleNamespace(
        pipelines={"live": SimpleNamespace(alive=True, config=RealtimePipelineConfig())},
    )
    server._app.camera_group_manager.camera_groups = {"capture": CameraPayload(id="capture", frame_number=10)}
    server._app.get_latest_aggregator_outputs = Mock()
    server._app.wait_for_realtime_result = AsyncMock()
    frame = await server._await_next_frame()
    assert frame.frame_number == 10 and frame.aggregator_output is None
    server._app.get_latest_aggregator_outputs.assert_not_called()
    server._app.wait_for_realtime_result.assert_not_awaited()


async def test_first_aggregator_result_does_not_delay_preview_or_reuse_dead_pipeline_output(server: WebsocketServer) -> None:
    server._app.realtime_pipeline_manager = SimpleNamespace(
        pipelines={"new": SimpleNamespace(alive=True, config=RealtimePipelineConfig())},
    )
    server._app.camera_group_manager.camera_groups = {"capture": CameraPayload(id="capture", frame_number=10)}
    server._app.get_latest_aggregator_outputs = Mock(return_value=[SimpleNamespace(pipeline_id="dead", frame_number=999)])
    server._app.wait_for_realtime_result = AsyncMock()
    frame = await server._await_next_frame()
    assert frame.frame_number == 10 and frame.aggregator_output is None
    server._app.wait_for_realtime_result.assert_not_awaited()


def retained_pipeline(server):
    """Real pipeline event/read code with deterministic subscriber delivery."""
    pipeline = RealtimePipeline.__new__(RealtimePipeline)
    pipeline.id = "live"
    pipeline.started = True
    pipeline.config = RealtimePipelineConfig()
    pipeline.camera_nodes = {}
    pipeline.aggregation_node = SimpleNamespace(is_alive=True)
    pipeline.skeleton_inference_node = None
    pipeline.charuco_recorder_node = None
    pipeline.camera_group = SimpleNamespace(error=None, get_frontend_payload_by_frame_number=Mock(
        side_effect=lambda *, frame_number, display_image_sizes: (b"matched", float(frame_number)),
    ))
    pipeline.result_ready_event = Event()
    pipeline.result_consumed_event = Event()
    pipeline.aggregation_output_subscription = Queue()
    pipeline._latest_aggregation_output = None
    server._app.realtime_pipeline_manager = SimpleNamespace(pipelines={"live": pipeline})

    def latest(*, if_newer_than):
        output = pipeline.get_latest_aggregator_output(if_newer_than)
        return [] if output is None else [output]

    server._app.get_latest_aggregator_outputs = latest
    server._app.wait_for_realtime_result = AsyncMock(wraps=pipeline.wait_for_result_ready)
    return pipeline


def completed_output(pipeline, number):
    return Mock(spec=AggregationNodeOutputMessage, pipeline_id="live", camera_group_id="capture",
                frame_number=number, pipeline_config=pipeline.config,
                # Empty tracking content is still a completed observation.
                camera_node_outputs={"camera": SimpleNamespace(skeleton_observation=SimpleNamespace(stages={}))})


async def test_ready_event_before_subscriber_delivery_never_interleaves_preview(server, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(websocket_server, "time", SimpleNamespace(perf_counter=lambda: clock[0]))
    pipeline = retained_pipeline(server)
    camera = CameraPayload(id="capture", frame_number=100)
    server._app.camera_group_manager.camera_groups = {"capture": camera}
    first = completed_output(pipeline, 1)
    pipeline.aggregation_output_subscription.put(first)
    pipeline.result_ready_event.set()
    assert (await server._await_next_frame()).aggregator_output is first

    # 20 FPS processed output, 30 FPS camera updates, 10 ms pubsub delivery lag.
    # Clock time is controlled; actual Event.wait/get_latest methods run.
    for number in range(2, 42):
        clock[0] += 0.04
        camera.frame_number = 100 + int((clock[0] - 100.0) * 30)
        pipeline.result_consumed_event.clear()
        pipeline.result_ready_event.set()
        # A level-triggered ready event wakes immediately while the queue is empty.
        assert await server._await_next_frame() is None
        assert pipeline.result_ready_event.is_set()
        assert not server._preview_mode
        clock[0] += 0.01
        output = completed_output(pipeline, number)
        pipeline.aggregation_output_subscription.put(output)
        frame = await server._await_next_frame()
        assert frame.aggregator_output is output and frame.frame_number == number
        assert pipeline.result_consumed_event.is_set()
        assert not pipeline.result_ready_event.is_set()
    assert server._camera_frame_cursors == {}
    assert server._app.wait_for_realtime_result.await_count == 40
    assert all(call.args[0] is not None for call in server._ensure_composition.await_args_list)


@pytest.mark.parametrize("expired", [False, True])
async def test_transient_missing_image_does_not_clear_processed_stream(server, monkeypatch, expired):
    clock = [100.0]
    monkeypatch.setattr(websocket_server, "time", SimpleNamespace(perf_counter=lambda: clock[0]))
    pipeline = retained_pipeline(server)
    server._app.camera_group_manager.camera_groups = {"capture": CameraPayload(id="capture", frame_number=100)}
    for number in (1, 2, 3):
        output = completed_output(pipeline, number)
        pipeline.aggregation_output_subscription.put(output)
        pipeline.result_ready_event.set()
        clock[0] += 0.05
        payload = pipeline.camera_group.get_frontend_payload_by_frame_number
        payload.side_effect = IndexError("expired") if number == 2 and expired else None
        payload.return_value = None if number == 2 else (b"matched", float(number))
        frame = await server._await_next_frame()
        if number == 2:
            assert frame is None
            assert not server._preview_mode
        else:
            assert frame.aggregator_output is output
    assert server._camera_frame_cursors == {}
    assert [call.args[0].frame_number for call in server._ensure_composition.await_args_list] == [1, 3]
