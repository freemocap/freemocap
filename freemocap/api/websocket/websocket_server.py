"""
WebSocket server with settings sync integration.
"""
import asyncio
import dataclasses
import json
import logging
import time
from queue import Empty
from typing import TYPE_CHECKING

import msgspec
import numpy as np
from fastapi import FastAPI
from skellycam.api.websocket.websocket_server import ServerFramerateCalculator
from skellylogs import get_websocket_log_queue
from skellylogs.handlers.websocket_log_queue_handler import MIN_LOG_LEVEL_FOR_WEBSOCKET
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from freemocap.api.websocket.tracker_schema_message import TrackerSchemasMessage, collect_active_tracker_schemas
from freemocap.api.websocket.websocket_message_types import WebsocketMessageType
from freemocap.app.freemocap_application import FreemocapApplication, get_freemocap_app

from freemocap.pubsub.pubsub_topics import PipelineTimingEvent, PipelineTimingMessage
from freemocap.core.pipeline.pipeline_timing_events import cap_events_by_frame_window
from freemocap.core.pipeline.pipeline_timing_task_ids import CLOCK_DOMAIN_PERF_COUNTER
from freemocap.utilities.wait_functions import await_10ms
from skellycam.core.types.type_overloads import CameraGroupIdString, FrameNumberInt
from skellycam.core.recorders.framerate_tracker import FramerateTracker, CurrentFramerate
try:
    from skellycam.core.types.frontend_payload_bytearray import (
        get_and_clear_frontend_preview_multiframe_samples,
        get_and_clear_frontend_preview_timing_samples,
    )
except ImportError:
    # Older skellycam builds may not expose preview timing drains yet.
    def get_and_clear_frontend_preview_timing_samples(_camera_group_id: str) -> dict[str, dict[str, list[float]]]:
        return {}

    def get_and_clear_frontend_preview_multiframe_samples(_camera_group_id: str) -> dict[str, list[float]]:
        return {}

logger = logging.getLogger(__name__)

BACKPRESSURE_WARNING_THRESHOLD: int = 300
# When outstanding acks exceed this, reset rather than stalling the pipeline indefinitely.
BACKPRESSURE_RESET_THRESHOLD: int = 300
PIPELINE_TIMING_FRAME_WINDOW: int = 3
PIPELINE_TIMING_FRAME_BUFFER: int = 2
METRICS_CLIENT_ROLE = "metrics"


def _parse_client_role(websocket: WebSocket) -> str:
    role = websocket.query_params.get("client_role", "full")
    return role.strip().lower() or "full"


def _merge_pipeline_timing_event(
        events: list[PipelineTimingEvent],
        msg: PipelineTimingMessage,
) -> int:
    dropped = int(msg.dropped_timing_events)
    if msg.events:
        events.extend(msg.events)
    return dropped


def _merge_pipeline_timing_sample(
        per_node: dict[str, dict[str, list[float]]],
        per_camera: dict[str, dict[str, list[float]]],
        msg: PipelineTimingMessage,
) -> None:
    if msg.node_kind == "camera" and msg.camera_id:
        cam_bucket = per_camera.setdefault(str(msg.camera_id), {})
        for stage, vals in msg.samples.items():
            cam_bucket.setdefault(stage, []).extend(vals)
    else:
        node_bucket = per_node.setdefault(msg.node_kind, {})
        for stage, vals in msg.samples.items():
            node_bucket.setdefault(stage, []).extend(vals)


def _msgspec_enc_hook(obj: object) -> object:
    """Fallback encoder for types msgspec doesn't natively handle.

    Handles Pydantic BaseModel instances (e.g. skellyforge's Point3d),
    dataclass instances, and numpy scalar types by converting them to
    their Python-native equivalents.
    """
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dataclass_fields__"):
        return dataclasses.asdict(obj)
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Cannot encode object of type {type(obj).__name__}")
# Reusable msgspec JSON encoder for all websocket JSON messages
_ws_json_encoder = msgspec.json.Encoder(enc_hook=_msgspec_enc_hook)


class FramerateMessage(msgspec.Struct):
    camera_group_id: CameraGroupIdString
    backend_framerate: CurrentFramerate
    frontend_framerate: CurrentFramerate
    message_type: WebsocketMessageType = WebsocketMessageType.FRAMERATE_UPDATE


def _configured_camera_fps_hz(pipeline: object | None) -> float | None:
    """Return a startup FPS scale only when all selected cameras specify one."""
    if pipeline is None:
        return None
    camera_ids = getattr(pipeline, "camera_ids", [])
    camera_configs = getattr(pipeline, "camera_configs", {})
    fps_values: list[float] = []
    for camera_id in camera_ids:
        config = camera_configs.get(camera_id)
        fps = getattr(config, "framerate", None)
        if fps is None or fps <= 0:
            return None
        fps_values.append(float(fps))
    if not fps_values:
        return None
    # A group timeline should span the slowest selected camera cadence.
    return min(fps_values)


class WebsocketServer:
    def __init__(self, fastapi_app: FastAPI, websocket: WebSocket):
        self.websocket = websocket
        self._client_role = _parse_client_role(websocket)
        self._metrics_only = self._client_role == METRICS_CLIENT_ROLE
        if not hasattr(fastapi_app, "state") or not hasattr(fastapi_app.state, "global_kill_flag"):
            raise RuntimeError(
                "FastAPI app does not have a global_kill_flag in its state"
            )
        self._global_kill_flag = fastapi_app.state.global_kill_flag
        self._app: FreemocapApplication = get_freemocap_app()

        self._websocket_should_continue = True
        self.ws_tasks: list[asyncio.Task] = []
        self.last_received_frontend_confirmation: FrameNumberInt = -1
        self.last_sent_frame_number: FrameNumberInt = -1
        self._display_image_sizes: dict[CameraGroupIdString, dict[str, float]] | None = None
        self._frontend_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}

        self._server_framerate_calculators: dict[CameraGroupIdString, ServerFramerateCalculator] = {}
        self._display_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}
        self._last_framerate_send_time: float = 0.0
        self._last_pipeline_timing_send_time: float = 0.0

        # Serialize all websocket sends — the `websockets` library does not
        # support concurrent writes on the same connection. Without this lock,
        # two tasks calling send_json/send_bytes at the same time hit an
        # internal `assert waiter is None or waiter.cancelled()` in the
        # protocol drain logic.
        self._send_lock = asyncio.Lock()

    async def _send_msgspec_json(self, data: object) -> None:
        """Encode any msgspec-compatible object to JSON and send as text."""
        async with self._send_lock:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_text(_ws_json_encoder.encode(data).decode("utf-8"))

    def _camera_group_ids_for_timing(self) -> set[CameraGroupIdString]:
        ids = set(self._app.camera_group_manager.camera_groups.keys())
        ids.update(self._server_framerate_calculators.keys())
        return ids

    def _build_pipeline_timing_payload(
            self,
            camera_group_id: CameraGroupIdString,
    ) -> dict[str, object] | None:
        """Drain preview JPEG/resize telemetry and optional pubsub pipeline stages."""
        if self._metrics_only:
            preview_by_cam = get_and_clear_frontend_preview_timing_samples(str(camera_group_id))
            multiframe_preview = get_and_clear_frontend_preview_multiframe_samples(str(camera_group_id))
        else:
            preview_by_cam = {}
            multiframe_preview = {}
        pipeline = self._app.get_realtime_pipeline_for_camera_group(camera_group_id)
        want_pubsub_timing = (
            pipeline is not None and pipeline.config.log_pipeline_times
        )

        per_node: dict[str, dict[str, list[float]]] = {}
        per_camera: dict[str, dict[str, list[float]]] = {}
        events: list[PipelineTimingEvent] = []
        dropped_timing_events = 0

        if want_pubsub_timing:
            sub = self._app.get_pipeline_timing_subscription(camera_group_id)
            if sub is not None:
                while True:
                    try:
                        msg: PipelineTimingMessage = sub.get_nowait()
                    except Empty:
                        break
                    _merge_pipeline_timing_sample(per_node, per_camera, msg)
                    dropped_timing_events += _merge_pipeline_timing_event(events, msg)

        if self._metrics_only:
            for cam_id, stages in preview_by_cam.items():
                for stage, samples in stages.items():
                    per_camera.setdefault(cam_id, {}).setdefault(stage, []).extend(samples)

            if multiframe_preview:
                mf_bucket = per_node.setdefault("multiframe", {})
                for stage, samples in multiframe_preview.items():
                    mf_bucket.setdefault(stage, []).extend(samples)

        capped_events, dropped_by_window = cap_events_by_frame_window(
            events,
            frame_window=PIPELINE_TIMING_FRAME_WINDOW,
            frame_buffer=PIPELINE_TIMING_FRAME_BUFFER,
        )
        dropped_timing_events += dropped_by_window

        if not per_node and not per_camera and not capped_events:
            return None
        return {
            "message_type": WebsocketMessageType.PIPELINE_TIMING.value,
            "camera_group_id": str(camera_group_id),
            "log_pipeline_times_enabled": want_pubsub_timing,
            "configured_camera_fps_hz": _configured_camera_fps_hz(pipeline),
            "per_node": per_node,
            "per_camera": per_camera,
            "events": [dataclasses.asdict(event) for event in capped_events],
            "clock_domain": CLOCK_DOMAIN_PERF_COUNTER,
            "relay_perf_counter_ns": time.perf_counter_ns(),
            "dropped_timing_events": dropped_timing_events,
        }

    async def __aenter__(self):
        logger.debug("Entering WebsocketRunner context manager...")
        self._websocket_should_continue = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("WebsocketRunner context manager exiting...")
        self._websocket_should_continue = False
        if self.websocket.client_state == WebSocketState.CONNECTED:
            try:
                await self.websocket.close()
            except RuntimeError:
                # Socket already closed by the client or a relay task
                pass
        for task in self.ws_tasks:
            if not task.done():
                task.cancel()
        logger.debug("WebsocketRunner context manager exited.")

    @property
    def should_continue(self):
        return (
                not self._global_kill_flag.value
                and self._websocket_should_continue
                and self.websocket.client_state == WebSocketState.CONNECTED
        )

    async def _send_tracker_schemas(self) -> None:
        """Send the active tracker definitions to the client.

        Called once on connect, before the image/payload relay starts. The
        frontend uses this to drive all skeleton rendering — connection lines,
        point styling, virtual-point resolution — without hardcoding tracker
        schemas.
        """
        try:
            message = TrackerSchemasMessage(schemas=collect_active_tracker_schemas())
            await self._send_msgspec_json(message)
            logger.debug(f"Sent tracker_schemas message ({list(message.schemas.keys())})")
        except Exception:
            logger.exception("Failed to send tracker_schemas handshake message")

    async def run(self):
        logger.info(
            "Starting websocket runner (client_role=%s)...",
            self._client_role,
        )
        if self._metrics_only:
            await self._run_metrics_only()
            return

        await self._send_tracker_schemas()
        self.ws_tasks = [
            asyncio.create_task(
                self._frontend_image_relay(),
                name="WebsocketFrontendImageRelay",
            ),
            asyncio.create_task(
                self._logs_relay(),
                name="WebsocketLogsRelay",
            ),
            asyncio.create_task(
                self._client_message_handler(),
                name="WebsocketClientMessageHandler",
            ),
        ]

        try:
            await asyncio.gather(*self.ws_tasks)
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            for task in self.ws_tasks:
                if not task.done():
                    task.cancel()
            raise

    async def _run_metrics_only(self) -> None:
        """Metrics window client: pipeline timing only, no image/log/posthoc relay."""
        self.ws_tasks = [
            asyncio.create_task(
                self._metrics_relay(),
                name="WebsocketMetricsRelay",
            ),
            asyncio.create_task(
                self._client_message_handler(),
                name="WebsocketClientMessageHandler",
            ),
        ]
        try:
            await asyncio.gather(*self.ws_tasks)
        except Exception as e:
            logger.exception(f"Error in metrics websocket runner: {e.__class__}: {e}")
            for task in self.ws_tasks:
                if not task.done():
                    task.cancel()
            raise

    async def _metrics_relay(self) -> None:
        logger.info("Starting metrics-only websocket relay...")
        try:
            while self.should_continue:
                now = time.perf_counter()
                if now - self._last_pipeline_timing_send_time >= 0.25:
                    for camera_group_id in self._camera_group_ids_for_timing():
                        timing_payload = self._build_pipeline_timing_payload(camera_group_id)
                        if timing_payload is not None:
                            await self._send_msgspec_json(timing_payload)
                    self._last_pipeline_timing_send_time = now
                await await_10ms()
        except WebSocketDisconnect:
            logger.api("Metrics client disconnected, ending metrics relay task...")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in metrics relay: {e.__class__}: {e}")
            self._websocket_should_continue = False
            raise

    def last_frame_acknowledged(self) -> bool:
        if self.last_sent_frame_number == -1:
            return True
        return self.last_received_frontend_confirmation >= self.last_sent_frame_number

    async def _frontend_image_relay(self) -> None:
        logger.info("Starting frontend image payload relay...")
        try:
            while self.should_continue:
                # Always drain and send posthoc progress — never gate this
                # behind backpressure. Progress messages are small JSON
                # payloads that don't cause the queue-growth problem that
                # backpressure is designed to prevent.
                posthoc_progress = self._app.posthoc_pipeline_manager.get_progress_updates()
                posthoc_progress.extend(self._app.posthoc_pipeline_manager.evict_completed())
                for update_message in posthoc_progress:
                    await self._send_msgspec_json(update_message)

                # Pipeline timing is small JSON — never gate behind frame ack backpressure.
                now = time.perf_counter()
                if now - self._last_pipeline_timing_send_time >= 0.25:
                    for camera_group_id in self._camera_group_ids_for_timing():
                        timing_payload = self._build_pipeline_timing_payload(camera_group_id)
                        if timing_payload is not None:
                            await self._send_msgspec_json(timing_payload)
                    self._last_pipeline_timing_send_time = now

                if not self.last_frame_acknowledged():
                    backpressure = self.last_sent_frame_number - self.last_received_frontend_confirmation
                    if backpressure >= BACKPRESSURE_RESET_THRESHOLD:
                        # Frontend is too far behind. Reset rather than stalling the aggregator
                        # indefinitely — a stalled aggregator causes camera-node queues to grow
                        # without bound and eventually OOM the process.
                        logger.warning(
                            f"Frontend ack lag reached {backpressure} frames "
                            f"(threshold={BACKPRESSURE_RESET_THRESHOLD}) — resetting ack counter"
                        )
                        self.last_received_frontend_confirmation = self.last_sent_frame_number
                        # Fall through to send the next frame.
                    else:
                        # Still within tolerable lag — yield and wait for the ack.
                        await await_10ms()
                        if backpressure > BACKPRESSURE_WARNING_THRESHOLD and backpressure % BACKPRESSURE_WARNING_THRESHOLD == 0:
                            logger.trace(f"Backpressure: {backpressure} frames unacknowledged")
                        continue

                # Ack received — block (off the event loop) until the
                # aggregator signals a processed frame is ready, then pull
                # and send immediately
                await self._app.wait_for_realtime_result(timeout=0.5)

                try:
                    packets, progress_updates = self._app.get_latest_frontend_payloads(if_newer_than=int(self.last_sent_frame_number))
                except IndexError:
                    logger.warning("Ring buffer overwrite — resetting to latest frame")
                    self.last_sent_frame_number = -1
                    continue

                for packet in packets:
                    if packet.frontend_payload is not None:
                        await self._send_msgspec_json(packet.frontend_payload)

                    if packet.keypoints_binary_payload is not None:
                        async with self._send_lock:
                            await self.websocket.send_bytes(packet.keypoints_binary_payload)

                    if packet.images_bytearray is not None:
                        async with self._send_lock:
                            await self.websocket.send_bytes(packet.images_bytearray)

                    self.last_sent_frame_number = packet.frame_number

                    # Server framerate: computed from frame_number + capture timestamp.
                    # frame_number increments by 1 per actual camera capture,
                    # multiframe_timestamp is perf_counter_ns at the camera grab.
                    # This gives the true capture rate even when frames are
                    # skipped in the websocket relay due to backpressure.
                    if packet.camera_group_id not in self._server_framerate_calculators:
                        self._server_framerate_calculators[packet.camera_group_id] = ServerFramerateCalculator(
                            source_name="Server")
                    self._server_framerate_calculators[packet.camera_group_id].update(
                        frame_number=packet.frame_number,
                        capture_timestamp_ns=float(packet.multiframe_timestamp),
                    )

                    # Display framerate: websocket send rate (what the UI actually receives)
                    if packet.camera_group_id not in self._display_framerate_trackers:
                        self._display_framerate_trackers[packet.camera_group_id] = FramerateTracker.create(
                            framerate_source="Display")
                    self._display_framerate_trackers[packet.camera_group_id].update(time.perf_counter_ns())

                for update_message in progress_updates:
                    await self._send_msgspec_json(update_message)

                # Send framerate updates from our local trackers (throttled to ~4Hz)
                now = time.perf_counter()
                if now - self._last_framerate_send_time >= 0.25:
                    for camera_group_id, server_calc in self._server_framerate_calculators.items():
                        if camera_group_id not in self._display_framerate_trackers:
                            continue
                        server_framerate = server_calc.current_framerate
                        display_tracker = self._display_framerate_trackers[camera_group_id]
                        if server_framerate and display_tracker.has_data:
                            framerate_message = FramerateMessage(
                                camera_group_id= camera_group_id,
                                backend_framerate= server_framerate,
                                frontend_framerate= display_tracker.current_framerate
                            )
                            await self._send_msgspec_json(framerate_message)
                            # Reset both trackers so the next report reflects only
                            # the interval since this report.
                            server_calc.clear()
                            display_tracker.clear()
                    self._last_framerate_send_time = now
        except WebSocketDisconnect:
            logger.api("Client disconnected, ending Frontend Image relay task...")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in frontend image relay: {e.__class__}: {e}")
            self._websocket_should_continue = False
            raise

    async def _logs_relay(self, ws_log_level: int = int(MIN_LOG_LEVEL_FOR_WEBSOCKET)):
        logger.info("Starting websocket log relay listener...")
        logs_queue = get_websocket_log_queue()
        try:
            while self.should_continue:
                if self.websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        # Skellycam's WebSocketQueueHandler puts LogRecordModel dicts
                        # into the queue via put_nowait(). On rare occasions a child
                        # process exit (cancel_join_thread) can leave a partial pickle
                        # in the pipe — EOFError/OSError handles that gracefully.
                        log_entry: dict = logs_queue.get_nowait()
                    except Empty:
                        await await_10ms()
                        continue
                    except (EOFError, OSError):
                        # Partial write from a dying child process — skip it
                        continue
                    if not isinstance(log_entry, dict):
                        continue
                    if log_entry.get("levelno", 0) < ws_log_level:
                        continue
                    async with self._send_lock:
                        await self.websocket.send_text(_ws_json_encoder.encode(log_entry).decode("utf-8"))
                else:
                    await await_10ms()
        except asyncio.CancelledError:
            logger.debug("Log relay task cancelled")
        except WebSocketDisconnect:
            logger.info("Client disconnected, ending log relay task...")
        except Exception as e:
            logger.exception(
                f"Error in websocket log relay: {e.__class__.__name__}: {e or '(no message)'} "
                f"— ws state: {self.websocket.client_state}"
            )
            self._websocket_should_continue = False
            raise

    async def _client_message_handler(self):
        """Handle messages from the client, including settings messages."""
        logger.info("Starting client message handler...")
        try:
            while self.should_continue:
                message = await self.websocket.receive()
                if message:
                    msg_type = message.get("type", "")

                    if msg_type == "websocket.disconnect":
                        logger.info(f"Received websocket disconnect (code={message.get('code', 'unknown')})")
                        self._websocket_should_continue = False
                        break

                    if "text" in message:
                        text_content = message.get("text", "")
                        if text_content.strip().startswith("{") or text_content.strip().startswith("["):
                            try:
                                data = json.loads(text_content)

                                # Route settings messages to the settings protocol
                                data_message_type = data.get("message_type", "")

                                if data_message_type == "client_handshake":
                                    role = str(data.get("client_role", "")).strip().lower()
                                    if role:
                                        self._client_role = role
                                        self._metrics_only = self._client_role == METRICS_CLIENT_ROLE
                                elif "frameNumber" in data:
                                    # Existing frame acknowledgment handling
                                    self.last_received_frontend_confirmation = data["frameNumber"]
                                    self._display_image_sizes = data.get("displayImageSizes", None)
                                else:
                                    logger.debug(f"Received unhandled JSON message: {list(data.keys())}")

                            except json.JSONDecodeError as e:
                                raise ValueError(f"Failed to decode JSON message: {e}") from e
                        else:
                            if text_content.startswith("ping"):
                                async with self._send_lock:
                                    await self.websocket.send_text("pong")
                            elif text_content.startswith("pong"):
                                pass
                            else:
                                logger.info(f"Websocket received message: `{text_content}`")
                    elif "bytes" in message:
                        logger.trace(f"Received binary websocket message ({len(message['bytes'])} bytes)")
                    else:
                        raise RuntimeError(f"Received unexpected message format: {message}")

        except asyncio.CancelledError:
            logger.debug("Client message handler task cancelled")
        except Exception as e:
            logger.exception(f"Error handling client message: {e.__class__}: {e}")
            self._websocket_should_continue = False
            raise
        finally:
            logger.info("Ending client message handler...")
