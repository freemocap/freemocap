"""Tests for pipeline timing task events and websocket payload conversion."""
from __future__ import annotations

from queue import Empty, Queue
from types import SimpleNamespace
from unittest.mock import MagicMock

import multiprocessing
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
    batch_task_id,
)
from freemocap.pubsub.pubsub_topics import PipelineTimingEvent, PipelineTimingMessage


# ═══════════════════════════════════════════════════════════════════════════════
# Task ID helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeterministicTaskIds:
    def test_batch_task_id(self) -> None:
        assert batch_task_id(
            frame_number=7,
            node_kind="skeleton_inference",
            stage="predict_batch",
        ) == "7:batch:skeleton_inference:predict_batch"


# ═══════════════════════════════════════════════════════════════════════════════
# tracker_events_to_pipeline_events
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrackerEventConversion:
    def test_from_dict_mapping(self) -> None:
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

    def test_from_pipeline_timing_event_passthrough(self) -> None:
        """Already-converted PipelineTimingEvent is returned as-is."""
        original = PipelineTimingEvent(
            task_id="5:batch:skeleton_inference:human_detection",
            stage="human_detection",
            node_kind="skeleton_inference",
            frame_number=5,
            duration_ms=2.0,
        )
        events = tracker_events_to_pipeline_events(
            [original],
            node_kind="skeleton_inference",
        )
        assert len(events) == 1
        assert events[0] is original

    def test_from_object_with_getattr(self) -> None:
        """Arbitrary object with matching attributes is converted."""
        obj = SimpleNamespace(
            task_id="3:batch:skeleton_inference:pose_estimation",
            parent_task_ids=["3:batch:skeleton_inference:frame_read"],
            stage="pose_estimation",
            node_kind="skeleton_inference",
            camera_id=None,
            frame_number=3,
            start_time_ns=100,
            end_time_ns=300,
            duration_ms=0.2,
            batch_index=None,
            batch_size=None,
        )
        events = tracker_events_to_pipeline_events(
            [obj],
            node_kind="skeleton_inference",
        )
        assert len(events) == 1
        assert events[0].task_id == "3:batch:skeleton_inference:pose_estimation"
        assert events[0].duration_ms == 0.2

    def test_skips_none_entries(self) -> None:
        events = tracker_events_to_pipeline_events(
            [None, {"task_id": "1:batch:skeleton_inference:x", "stage": "x"}],
            node_kind="skeleton_inference",
        )
        assert len(events) == 1

    def test_string_parent_task_ids_wrapped_in_list(self) -> None:
        events = tracker_events_to_pipeline_events(
            [{
                "task_id": "1:batch:skeleton_inference:y",
                "parent_task_ids": "single_string_parent",
                "stage": "y",
            }],
            node_kind="skeleton_inference",
        )
        assert len(events) == 1
        assert events[0].parent_task_ids == ["single_string_parent"]

    # ── RTMPose synthesis ─────────────────────────────────────────────────

    def test_synthesize_rtmpose_batch_events_from_legacy_attrs(self) -> None:
        session = SimpleNamespace(
            last_human_detection_letterbox_ms=0.4,
            last_human_detection_batch_pack_ms=0.6,
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
        assert len(events) == 8
        assert [event.stage for event in events[:3]] == [
            "human_detection_letterbox",
            "human_detection_batch_pack",
            "human_detection_preprocess",
        ]
        preprocess = next(event for event in events if event.stage == "human_detection_preprocess")
        letterbox = next(event for event in events if event.stage == "human_detection_letterbox")
        batch_pack = next(event for event in events if event.stage == "human_detection_batch_pack")
        predict_batch_id = batch_task_id(
            frame_number=5,
            node_kind="skeleton_inference",
            stage="predict_batch",
        )
        assert letterbox.parent_task_ids == [preprocess.task_id]
        assert batch_pack.parent_task_ids == [preprocess.task_id]
        assert preprocess.parent_task_ids == [predict_batch_id]
        # After sorting by stage order, events[0] is letterbox (parent=preprocess).
        assert events[0].stage == "human_detection_letterbox"
        assert events[0].parent_task_ids == [preprocess.task_id]
        assert preprocess.start_time_ns == letterbox.start_time_ns
        assert preprocess.end_time_ns == batch_pack.end_time_ns
        assert events[0].start_time_ns == 1_000_000
        assert events[-1].end_time_ns > events[0].start_time_ns
        assert events[0].batch_size == 2

    def test_synthesize_rtmpose_batch_events_all_zero_durations(self) -> None:
        """When every ``last_*_ms`` is zero the result must be an empty list."""
        session = SimpleNamespace(
            last_human_detection_letterbox_ms=0.0,
            last_human_detection_batch_pack_ms=0.0,
            last_human_detection_preprocess_ms=0.0,
            last_human_detection_ms=0.0,
            last_human_detection_postprocess_ms=0.0,
            last_pose_estimation_preprocess_ms=0.0,
            last_pose_estimation_ms=0.0,
            last_pose_estimation_postprocess_ms=0.0,
        )
        events = synthesize_rtmpose_batch_events(
            session,
            frame_number=5,
            node_kind="skeleton_inference",
        )
        assert events == []

    def test_synthesize_rtmpose_with_missing_attrs(self) -> None:
        """Session missing the timing attributes returns empty list."""
        session = SimpleNamespace()  # no last_*_ms attrs
        events = synthesize_rtmpose_batch_events(
            session,
            frame_number=5,
            node_kind="skeleton_inference",
        )
        assert events == []

    # ── collect_tracker_batch_events ──────────────────────────────────────

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

    def test_collect_tracker_batch_events_falls_back_to_batch_timing_events(self) -> None:
        session = SimpleNamespace(
            batch_timing_events=[
                PipelineTimingEvent(
                    task_id="4:batch:skeleton_inference:pose_estimation",
                    stage="pose_estimation",
                    node_kind="skeleton_inference",
                    frame_number=4,
                    duration_ms=1.5,
                ),
            ],
        )
        events = collect_tracker_batch_events(
            session,
            node_kind="skeleton_inference",
            frame_number=4,
        )
        assert len(events) == 1
        assert events[0].stage == "pose_estimation"

    def test_collect_tracker_batch_events_falls_back_to_synthesis(self) -> None:
        """When no events are available, falls through to legacy synthesis."""
        session = SimpleNamespace(
            last_human_detection_ms=2.0,
        )
        events = collect_tracker_batch_events(
            session,
            node_kind="skeleton_inference",
            frame_number=7,
        )
        # Synthesis produces at least the stage that has a positive duration.
        assert len(events) >= 1
        assert any(e.stage == "human_detection" for e in events)


# ═══════════════════════════════════════════════════════════════════════════════
# PipelineStageTimer
# ═══════════════════════════════════════════════════════════════════════════════

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

    def test_record_simple_elapsed_ms(self) -> None:
        timer = PipelineStageTimer(name="test")
        timer.record("predict_batch", 12.5)
        timer.record("predict_batch", 7.5)
        assert timer.samples["predict_batch"] == [12.5, 7.5]

    def test_maybe_flush_publishes_and_clears(self) -> None:
        timer = PipelineStageTimer(name="test_node", flush_interval=0.0)
        pub_queue: multiprocessing.Queue = multiprocessing.Queue()

        # Accumulate one event (record_task_event also records the duration sample).
        timer.record_task_event(
            PipelineTimingEvent(
                task_id="1:batch:skeleton_inference:predict_batch",
                stage="predict_batch",
                node_kind="skeleton_inference",
                frame_number=1,
                duration_ms=3.0,
            ),
        )
        timer.dropped_events = 2  # simulate prior drops

        timer.maybe_flush(
            publication_queue=pub_queue,
            node_kind="skeleton_inference",
            camera_id="cam_0",
        )

        assert not pub_queue.empty()
        msg: PipelineTimingMessage = pub_queue.get_nowait()
        assert msg.node_kind == "skeleton_inference"
        assert msg.node_label == "test_node"
        assert msg.camera_id == "cam_0"
        assert msg.samples == {"predict_batch": [3.0]}
        assert len(msg.events) == 1
        assert msg.dropped_timing_events == 2

        # Internal state is cleared after flush.
        assert timer.samples["predict_batch"] == []
        assert timer.events == []
        assert timer.dropped_events == 0

    def test_maybe_flush_skips_when_empty(self) -> None:
        timer = PipelineStageTimer(name="test", flush_interval=0.0)
        pub_queue: multiprocessing.Queue = multiprocessing.Queue()
        timer.maybe_flush(publication_queue=pub_queue, node_kind="test")
        assert pub_queue.empty()


# ═══════════════════════════════════════════════════════════════════════════════
# cap_events_by_frame_window
# ═══════════════════════════════════════════════════════════════════════════════

class TestCapEventsByFrameWindow:
    def test_keeps_latest_frames(self) -> None:
        events = [
            PipelineTimingEvent(task_id=f"{frame}:agg:x", stage="x", node_kind="aggregator", frame_number=frame)
            for frame in range(10)
        ]
        kept, dropped = cap_events_by_frame_window(events, frame_window=3, frame_buffer=0)
        assert dropped == 7
        assert {event.frame_number for event in kept} == {7, 8, 9}


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket pipeline timing payload
# ═══════════════════════════════════════════════════════════════════════════════

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
                node_kind="skeleton_inference",
                samples={"predict_batch": [12.5]},
                events=[
                    PipelineTimingEvent(
                        task_id="4:batch:skeleton_inference:predict_batch",
                        stage="predict_batch",
                        node_kind="skeleton_inference",
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
        assert payload["events"][0]["task_id"] == "4:batch:skeleton_inference:predict_batch"
        assert payload["per_node"]["skeleton_inference"]["predict_batch"] == [12.5]

    def test_build_payload_drains_multiple_messages(self) -> None:
        server = self._make_server()
        sub = server._app.get_pipeline_timing_subscription.return_value
        sub.put_nowait(
            PipelineTimingMessage(
                node_kind="skeleton_inference",
                samples={"predict_batch": [8.0]},
                events=[
                    PipelineTimingEvent(
                        task_id="5:batch:skeleton_inference:predict_batch",
                        stage="predict_batch",
                        node_kind="skeleton_inference",
                        frame_number=5,
                        duration_ms=8.0,
                    ),
                ],
                dropped_timing_events=1,
            ),
        )
        payload = server._build_pipeline_timing_payload("group_a")
        assert payload is not None
        assert len(payload["events"]) == 2
        assert payload["dropped_timing_events"] == 3  # 2 + 1
        assert payload["per_node"]["skeleton_inference"]["predict_batch"] == [12.5, 8.0]

    def test_payload_encoder_handles_numpy_string_scalars(self) -> None:
        payload = {
            "message_type": "pipeline_timing",
            "camera_group_id": np.str_("group_a"),
            "events": [
                {
                    "task_id": np.str_("4:batch:skeleton_inference:predict_batch"),
                    "stage": np.str_("predict_batch"),
                    "duration_ms": np.float64(1.25),
                },
            ],
        }
        encoded = _ws_json_encoder.encode(payload).decode("utf-8")
        assert '"camera_group_id":"group_a"' in encoded

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

    def test_merge_sample_routes_camera_node_kind_to_per_camera(self) -> None:
        per_node: dict[str, dict[str, list[float]]] = {}
        per_camera: dict[str, dict[str, list[float]]] = {}
        msg = PipelineTimingMessage(
            node_kind="camera",
            camera_id="cam_0",
            samples={"frame_read": [5.0, 7.0]},
        )
        _merge_pipeline_timing_sample(per_node, per_camera, msg)
        assert per_node == {}
        assert per_camera["cam_0"]["frame_read"] == [5.0, 7.0]

    def test_metrics_client_role_flag(self) -> None:
        server = self._make_server(metrics_only=True)
        assert server._metrics_only is True
        assert server._client_role == METRICS_CLIENT_ROLE
