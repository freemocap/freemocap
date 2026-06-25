"""Tests for pipeline timing task events and websocket payload conversion."""
from __future__ import annotations

from queue import Queue
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from starlette.websockets import WebSocket, WebSocketState

from freemocap.api.websocket.websocket_server import (
    METRICS_CLIENT_ROLE,
    WebsocketServer,
    _merge_pipeline_timing_event,
    _merge_pipeline_timing_sample,
    _ws_json_encoder,
)
from freemocap.core.pipeline.pipeline_stage_timer import MAX_EVENTS_PER_FLUSH, PipelineStageTimer
from freemocap.core.pipeline.pipeline_timing_events import (
    cap_events_by_frame_window,
    collect_tracker_batch_events,
    synthesize_rtmpose_batch_events,
    tracker_events_to_pipeline_events,
)
from freemocap.core.pipeline.pipeline_timing_task_ids import (
    aggregator_task_id,
    batch_task_id,
    per_camera_task_id,
)
from freemocap.pubsub.pubsub_topics import PipelineTimingEvent, PipelineTimingMessage


class TestDeterministicTaskIds:
    def test_per_camera_task_id(self) -> None:
        assert per_camera_task_id(
            frame_number=42,
            camera_id="cam_0",
            node_kind="camera",
            stage="skeleton_detection",
        ) == "42:cam_0:camera:skeleton_detection"

    def test_batch_task_id(self) -> None:
        assert batch_task_id(
            frame_number=7,
            node_kind="skeleton_inference",
            stage="predict_batch",
        ) == "7:batch:skeleton_inference:predict_batch"

    def test_aggregator_task_id(self) -> None:
        assert aggregator_task_id(frame_number=9, stage="full_frame_processing") == (
            "9:aggregator:full_frame_processing"
        )


class TestTrackerEventConversion:
    def test_tracker_events_to_pipeline_events_from_mapping(self) -> None:
        events = tracker_events_to_pipeline_events(
            [
                {
                    "task_id": "1:batch:skeleton_inference:pose_estimation",
                    "parent_task_ids": ["1:batch:skeleton_inference:frame_read"],
                    "stage": "pose_estimation",
                    "frame_number": 1,
                    "start_time_ns": 100,
                    "end_time_ns": 250,
                    "duration_ms": 0.15,
                },
            ],
            node_kind="skeleton_inference",
        )
        assert len(events) == 1
        assert events[0].task_id.endswith("pose_estimation")
        assert events[0].parent_task_ids == ["1:batch:skeleton_inference:frame_read"]

    def test_synthesize_rtmpose_batch_events_from_legacy_attrs(self) -> None:
        session = SimpleNamespace(
            last_human_detection_preprocess_ms=1.0,
            last_human_detection_ms=2.0,
            last_human_detection_postprocess_ms=0.5,
            last_pose_estimation_preprocess_ms=1.5,
            last_pose_estimation_ms=3.0,
            last_pose_estimation_postprocess_ms=0.25,
        )
        events = synthesize_rtmpose_batch_events(
            session,
            frame_number=5,
            node_kind="skeleton_inference",
            camera_ids=["cam_0", "cam_1"],
            batch_parent_task_id="5:batch:skeleton_inference:frame_read",
            batch_start_time_ns=1_000_000,
        )
        assert len(events) == 6
        assert events[0].parent_task_ids == ["5:batch:skeleton_inference:frame_read"]
        assert events[0].start_time_ns == 1_000_000
        assert events[-1].end_time_ns > events[0].start_time_ns
        assert events[0].batch_size == 2

    def test_collect_tracker_batch_events_prefers_session_events(self) -> None:
        session = SimpleNamespace(
            last_batch_timing_events=[
                PipelineTimingEvent(
                    task_id="3:batch:skeleton_inference:human_detection",
                    stage="human_detection",
                    node_kind="skeleton_inference",
                    frame_number=3,
                    start_time_ns=10,
                    end_time_ns=20,
                    duration_ms=0.01,
                ),
            ],
            last_human_detection_ms=99.0,
        )
        events = collect_tracker_batch_events(
            session,
            node_kind="skeleton_inference",
            frame_number=3,
        )
        assert len(events) == 1
        assert events[0].stage == "human_detection"


class TestDroppedEventAccounting:
    def test_timer_drops_events_when_buffer_full(self) -> None:
        timer = PipelineStageTimer(name="test")
        for index in range(MAX_EVENTS_PER_FLUSH + 5):
            timer.record_task_event(
                PipelineTimingEvent(
                    task_id=f"{index}:batch:test:stage",
                    stage="stage",
                    node_kind="test",
                    frame_number=index,
                    duration_ms=1.0,
                ),
            )
        assert len(timer.events) == MAX_EVENTS_PER_FLUSH
        assert timer.dropped_events == 5

    def test_cap_events_by_frame_window(self) -> None:
        events = [
            PipelineTimingEvent(task_id=f"{frame}:agg:x", stage="x", node_kind="aggregator", frame_number=frame)
            for frame in range(10)
        ]
        kept, dropped = cap_events_by_frame_window(events, frame_window=3, frame_buffer=0)
        assert dropped == 7
        assert {event.frame_number for event in kept} == {7, 8, 9}


class TestWebsocketPipelineTimingPayload:
    @staticmethod
    def _make_server(*, metrics_only: bool = False) -> WebsocketServer:
        websocket = MagicMock(spec=WebSocket)
        websocket.query_params = {"client_role": METRICS_CLIENT_ROLE if metrics_only else "full"}
        websocket.client_state = WebSocketState.CONNECTED
        mock_app = MagicMock()
        mock_app.camera_group_manager.camera_groups = {"group_a": object()}
        pipeline = MagicMock()
        pipeline.config.log_pipeline_times = True
        pipeline.camera_ids = ["cam_0", "cam_1"]
        pipeline.camera_configs = {
            "cam_0": SimpleNamespace(framerate=30.0),
            "cam_1": SimpleNamespace(framerate=20.0),
        }
        mock_app.get_realtime_pipeline_for_camera_group.return_value = pipeline
        sub = Queue()
        sub.put_nowait(
            PipelineTimingMessage(
                node_kind="camera",
                camera_id="cam_0",
                samples={"skeleton_detection": [12.5]},
                events=[
                    PipelineTimingEvent(
                        task_id="4:cam_0:camera:skeleton_detection",
                        stage="skeleton_detection",
                        node_kind="camera",
                        camera_id="cam_0",
                        frame_number=4,
                        start_time_ns=100,
                        end_time_ns=200,
                        duration_ms=0.1,
                    ),
                ],
                dropped_timing_events=2,
            ),
        )
        mock_app.get_pipeline_timing_subscription.return_value = sub
        server = object.__new__(WebsocketServer)
        server.websocket = websocket
        server._client_role = METRICS_CLIENT_ROLE if metrics_only else "full"
        server._metrics_only = metrics_only
        server._app = mock_app
        server._global_kill_flag = SimpleNamespace(value=False)
        server._websocket_should_continue = True
        server.ws_tasks = []
        server._last_pipeline_timing_send_time = 0.0
        return server

    def test_build_payload_includes_task_events_and_clock_metadata(self) -> None:
        server = self._make_server()
        payload = server._build_pipeline_timing_payload("group_a")
        assert payload is not None
        assert payload["clock_domain"] == "perf_counter"
        assert isinstance(payload["relay_perf_counter_ns"], int)
        assert payload["realtime_pipeline_active"] is True
        assert payload["dropped_timing_events"] == 2
        assert payload["configured_camera_fps_hz"] == 20.0
        assert len(payload["events"]) == 1
        assert payload["events"][0]["task_id"] == "4:cam_0:camera:skeleton_detection"
        assert payload["per_camera"]["cam_0"]["skeleton_detection"] == [12.5]

    def test_payload_encoder_handles_numpy_string_scalars(self) -> None:
        payload = {
            "message_type": "pipeline_timing",
            "camera_group_id": np.str_("group_a"),
            "events": [
                {
                    "task_id": np.str_("4:cam_0:camera:skeleton_detection"),
                    "camera_id": np.str_("cam_0"),
                    "stage": np.str_("skeleton_detection"),
                    "duration_ms": np.float64(1.25),
                },
            ],
        }
        encoded = _ws_json_encoder.encode(payload).decode("utf-8")
        assert '"camera_group_id":"group_a"' in encoded
        assert '"camera_id":"cam_0"' in encoded

    def test_metrics_only_sends_status_when_pipeline_active_without_samples(self) -> None:
        server = self._make_server(metrics_only=True)
        server._app.get_pipeline_timing_subscription.return_value = Queue()
        payload = server._build_pipeline_timing_payload("group_a")
        assert payload is not None
        assert payload["realtime_pipeline_active"] is True
        assert payload["events"] == []

    def test_metrics_only_sends_inactive_status_without_pipeline(self) -> None:
        server = self._make_server(metrics_only=True)
        server._app.get_realtime_pipeline_for_camera_group.return_value = None
        server._app.get_pipeline_timing_subscription.return_value = Queue()
        payload = server._build_pipeline_timing_payload("group_a")
        assert payload is not None
        assert payload["realtime_pipeline_active"] is False

    def test_metrics_only_includes_preview_timing_samples(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "freemocap.api.websocket.websocket_server.get_and_clear_frontend_preview_timing_samples",
            lambda _group: {"cam_0": {"jpeg_resize": [1.0]}},
        )
        monkeypatch.setattr(
            "freemocap.api.websocket.websocket_server.get_and_clear_frontend_preview_multiframe_samples",
            lambda _group: {"preview": [2.0]},
        )
        server = self._make_server(metrics_only=True)
        payload = server._build_pipeline_timing_payload("group_a")
        assert payload is not None
        assert payload["per_camera"]["cam_0"]["jpeg_resize"] == [1.0]
        assert payload["per_node"]["multiframe"]["preview"] == [2.0]

    def test_merge_helpers_accumulate_samples_and_events(self) -> None:
        per_node: dict[str, dict[str, list[float]]] = {}
        per_camera: dict[str, dict[str, list[float]]] = {}
        events: list[PipelineTimingEvent] = []
        msg = PipelineTimingMessage(
            node_kind="skeleton_inference",
            samples={"predict_batch": [3.0]},
            events=[
                PipelineTimingEvent(task_id="1:batch:skeleton_inference:predict_batch", stage="predict_batch"),
            ],
            dropped_timing_events=1,
        )
        _merge_pipeline_timing_sample(per_node, per_camera, msg)
        dropped = _merge_pipeline_timing_event(events, msg)
        assert per_node["skeleton_inference"]["predict_batch"] == [3.0]
        assert len(events) == 1
        assert dropped == 1

    def test_metrics_client_role_flag(self) -> None:
        server = self._make_server(metrics_only=True)
        assert server._metrics_only is True
        assert server._client_role == METRICS_CLIENT_ROLE
