"""
WebSocket server with settings sync integration.

Thin supervisor for one WebSocket connection: composes the standard-stream
send path (SendSerializer + FrameRelay + BackpressureController) with the
image relay, log relay, app-state sender, and the inbound client-message
handler (settings sync + frame acks + display sizes).

The standard-stream send path (schema once, then binary samples) replaced the
legacy binary-keypoints protocol (D36). Image data stays a separate JPEG
bytearray stream, linked by frame number.
"""
import asyncio
import json
import logging
import os
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

from freemocap.api.websocket.backpressure_controller import BackpressureController
from freemocap.api.websocket.frame_relay import FrameRelay, lengths_differ_materially, schema_bytes
from freemocap.api.websocket.send_serializer import SendSerializer
from freemocap.api.websocket.websocket_message_types import WebsocketMessageType
from freemocap.app.freemocap_application import FreemocapApplication, get_freemocap_app
from freemocap.core.streaming.standard_stream import StreamSchema
from freemocap.utilities.wait_functions import await_10ms
from skellyforge.skellymodels.standard_human.standard_human_model import compose_standard_human
from skellycam.core.types.type_overloads import CameraGroupIdString, FrameNumberInt
from skellycam.core.recorders.framerate_tracker import FramerateTracker, CurrentFramerate

if TYPE_CHECKING:
    from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage

logger = logging.getLogger(__name__)


class FramerateMessage(msgspec.Struct):
    camera_group_id: CameraGroupIdString
    backend_framerate: CurrentFramerate
    frontend_framerate: CurrentFramerate
    message_type: WebsocketMessageType = WebsocketMessageType.FRAMERATE_UPDATE


class WebsocketServer:
    def __init__(self, fastapi_app: FastAPI, websocket: WebSocket):
        self.websocket = websocket
        if not hasattr(fastapi_app, "state") or not hasattr(fastapi_app.state, "global_kill_flag"):
            raise RuntimeError(
                "FastAPI app does not have a global_kill_flag in its state"
            )
        self._global_kill_flag = fastapi_app.state.global_kill_flag
        self._app: FreemocapApplication = get_freemocap_app()

        self._websocket_should_continue = True
        self.ws_tasks: list[asyncio.Task] = []
        self.last_received_frontend_confirmation: FrameNumberInt = -1
        self._display_image_sizes: dict[CameraGroupIdString, dict[str, float]] | None = None

        self._frontend_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}
        self._server_framerate_calculators: dict[CameraGroupIdString, ServerFramerateCalculator] = {}
        self._display_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}
        self._last_framerate_send_time: float = 0.0

        # ── Standard-stream send path ────────────────────────────────────
        # One writer (the serializer owns the send lock).
        self._serializer = SendSerializer(websocket)
        # Ack window: 3 frames in flight before waiting; reset at 300 behind.
        self._backpressure = BackpressureController(window_size=3, reset_threshold=300)
        # Schema built once at connect, re-built on a camera-topology change.
        self._standard_human = compose_standard_human()
        self._schema: StreamSchema
        self._schema_camera_ids: tuple[str, ...] = ()
        self._schema_segment_lengths: dict[str, float] | None = None
        self._build_schema()
        # The relay consumes raw aggregator output via the injected source.
        self._relay = FrameRelay(
            serializer=self._serializer,
            backpressure=self._backpressure,
            schema=self._schema,
            standard_human=self._standard_human,
            source=self._await_next_aggregator_output,
        )

    def _current_camera_ids(self) -> tuple[str, ...]:
        """The sorted camera IDs across all live realtime pipelines.

        This is the schema's ``camera_ids`` — the honest driver of the schema-
        change trigger (a new pipeline run with a different camera set).
        """
        ids: set[str] = set()
        for pipeline in self._app.realtime_pipeline_manager.pipelines.values():
            ids.update(pipeline.camera_ids)
        return tuple(sorted(ids))

    def _build_schema(self, segment_lengths: dict[str, float] | None = None) -> None:
        """Build (or rebuild) the standard-stream schema for the current topology.

        The schema is immutable; the only things that can change at runtime are
        the camera set (a new realtime pipeline run) and the measured segment
        lengths (the estimators converging). Both are honest schema-change
        triggers: the schema is re-built — and re-sent — when ``camera_ids``
        differs from what it was built with, or when ``segment_lengths`` has
        changed materially. ``segment_lengths=None`` yields the anthropometric
        defaults (``length_ratio × NOMINAL_SUBJECT_HEIGHT_MM``) — the first send
        on connect.
        """
        camera_ids = self._current_camera_ids()
        self._schema = StreamSchema.from_standard_human(
            stream_id=f"freemocap-{os.getpid()}",
            stream_name="freemocap standard stream",
            standard_human=self._standard_human,
            camera_ids=camera_ids,
            measured_lengths=segment_lengths,
        )
        self._schema_camera_ids = camera_ids
        self._schema_segment_lengths = dict(segment_lengths) if segment_lengths else None

    # ── Frame source (wired to the app) ─────────────────────────────────
    async def _await_next_aggregator_output(self) -> "AggregationNodeOutputMessage | None":
        """Wait for a new aggregator output, then pull the newest one.

        This is the relay's frame source: same wake-up primitive the old relay
        used, but pulling the *raw aggregator output* (the standard-stream
        encoder input) rather than a rendered FrontendImagePacket.
        """
        await self._app.wait_for_realtime_result(timeout=0.5)

        # Re-check topology each wake-up; rebuild + resend the schema if the
        # camera set changed (a new pipeline run).
        if self._check_schema_change():
            self._build_schema()
            self._relay.set_schema(self._schema)
            await self._serializer.send_schema_json(schema_bytes(self._schema))

        outputs = self._app.get_latest_aggregator_outputs(
            if_newer_than=self._relay.last_sent_frame_number,
        )
        if not outputs:
            return None
        # One pipeline per camera set today; take the newest frame_number.
        newest = max(outputs, key=lambda m: m.frame_number)

        # Segment lengths are carried per frame. When they change materially
        # (first arrival, or any segment moves > threshold), rebuild + resend the
        # schema with the measured lengths so the frontend converges to the live
        # estimates.
        if lengths_differ_materially(
            self._schema_segment_lengths, newest.segment_lengths
        ):
            self._build_schema(segment_lengths=newest.segment_lengths)
            self._relay.set_schema(self._schema)
            await self._serializer.send_schema_json(schema_bytes(self._schema))

        return newest

    def _check_schema_change(self) -> bool:
        return self._current_camera_ids() != self._schema_camera_ids

    # ── JSON send helper (retained for non-sample messages) ────────────
    async def _send_msgspec_json(self, data: object) -> None:
        await self._serializer.send_json(data)

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

    async def run(self):
        logger.info("Starting websocket runner...")
        # Schema first, on connect — the frontend indexes sample blocks by it.
        await self._serializer.send_schema_json(schema_bytes(self._schema))
        self.ws_tasks = [
            asyncio.create_task(self._relay.run(), name="WebsocketStandardStreamRelay"),
            asyncio.create_task(self._image_relay(), name="WebsocketFrontendImageRelay"),
            asyncio.create_task(self._logs_relay(), name="WebsocketLogsRelay"),
            asyncio.create_task(self._client_message_handler(), name="WebsocketClientMessageHandler"),
            asyncio.create_task(self._app_state_sender(), name="WebsocketAppStateSender"),
        ]

        try:
            await asyncio.gather(*self.ws_tasks)
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            for task in self.ws_tasks:
                if not task.done():
                    task.cancel()
            raise

    async def _app_state_sender(self):
        logger.info("Starting app-state sender task...")
        previous_state: dict | None = None
        try:
            while self.should_continue:
                state_dict = self._app.to_state_dict()
                if previous_state is None or state_dict != previous_state:
                    await self._send_msgspec_json({
                        "message_type": WebsocketMessageType.APP_STATE,
                        "server_pid": os.getpid(),
                        "state": state_dict,
                    })
                await asyncio.sleep(1.0)
                previous_state = state_dict
        except asyncio.CancelledError:
            pass
        except WebSocketDisconnect:
            logger.info("Client disconnected, ending app-state sender task...")
        except Exception as e:
            logger.exception(f"Error in app-state sender: {e.__class__}: {e}")
            self._websocket_should_continue = False
            self._global_kill_flag.value = True
            raise

    async def _image_relay(self) -> None:
        """Relay JPEG image bytearrays alongside the standard stream.

        Image data stays separate (doc 02 § Goal 4): images are keyed by frame
        number and sent via ``send_bytes`` on any *new* frame, but never gated
        by the standard-stream ack window. Skips when there are no realtime
        pipelines producing images (camera-only path is preserved too).
        """
        logger.info("Starting frontend image relay...")
        last_sent_img: FrameNumberInt = -1
        try:
            while self.should_continue:
                packets, progress_updates = self._app.get_latest_frontend_payloads(
                    if_newer_than=last_sent_img,
                    display_image_sizes=self._display_image_sizes,
                )
                for packet in packets:
                    if packet.images_bytearray is not None:
                        await self._serializer.send_raw_bytes(packet.images_bytearray)
                    last_sent_img = packet.frame_number
                    self._record_framerate(packet)
                for update_message in progress_updates:
                    await self._send_msgspec_json(update_message)
                await self._send_framerate_updates()
                await await_10ms()
        except WebSocketDisconnect:
            logger.api("Client disconnected, ending image relay task...")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in image relay: {e.__class__}: {e}")
            self._websocket_should_continue = False
            self._global_kill_flag.value = True
            raise

    def _record_framerate(self, packet) -> None:
        camera_group_id = packet.camera_group_id
        frame_number = packet.frame_number
        if camera_group_id not in self._server_framerate_calculators:
            self._server_framerate_calculators[camera_group_id] = ServerFramerateCalculator(
                source_name="Server")
        self._server_framerate_calculators[camera_group_id].update(
            frame_number=frame_number,
            capture_timestamp_ns=float(packet.multiframe_timestamp),
        )
        if camera_group_id not in self._display_framerate_trackers:
            self._display_framerate_trackers[camera_group_id] = FramerateTracker.create(
                framerate_source="Display")
        self._display_framerate_trackers[camera_group_id].update(time.perf_counter_ns())

    async def _send_framerate_updates(self) -> None:
        now = time.perf_counter()
        if now - self._last_framerate_send_time < 0.25:
            return
        for camera_group_id, server_calc in self._server_framerate_calculators.items():
            if camera_group_id not in self._display_framerate_trackers:
                continue
            server_framerate = server_calc.current_framerate
            display_tracker = self._display_framerate_trackers[camera_group_id]
            if server_framerate and display_tracker.has_data:
                framerate_message = FramerateMessage(
                    camera_group_id=camera_group_id,
                    backend_framerate=server_framerate,
                    frontend_framerate=display_tracker.current_framerate,
                )
                await self._send_msgspec_json(framerate_message)
                server_calc.clear()
                display_tracker.clear()
        self._last_framerate_send_time = now

    async def _logs_relay(self, ws_log_level: int = int(MIN_LOG_LEVEL_FOR_WEBSOCKET)):
        logger.info("Starting websocket log relay listener...")
        logs_queue = get_websocket_log_queue()
        try:
            while self.should_continue:
                if self.websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        log_entry: dict = logs_queue.get_nowait()
                    except Empty:
                        await await_10ms()
                        continue
                    except (EOFError, OSError):
                        continue
                    if not isinstance(log_entry, dict):
                        continue
                    if log_entry.get("levelno", 0) < ws_log_level:
                        continue
                    await self._serializer.send_json(log_entry)
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
            self._global_kill_flag.value = True
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
                                data_message_type = data.get("message_type", "")

                                if "frameNumber" in data:
                                    # Frame ack → free standard-stream ack window.
                                    self._relay.ack(data["frameNumber"])
                                    self.last_received_frontend_confirmation = data["frameNumber"]
                                    raw_sizes = data.get("displayImageSizes", None)
                                    if raw_sizes is not None:
                                        parsed = {
                                            cam_id: {k: float(v) for k, v in dims.items()}
                                            for cam_id, dims in raw_sizes.items()
                                        }
                                        self._display_image_sizes = {
                                            cam_id: dims
                                            for cam_id, dims in parsed.items()
                                            if dims.get("width", 0) > 0 and dims.get("height", 0) > 0
                                        } or None
                                    else:
                                        self._display_image_sizes = None
                                else:
                                    logger.debug(f"Received unhandled JSON message: {list(data.keys())}")

                            except json.JSONDecodeError as e:
                                raise ValueError(f"Failed to decode JSON message: {e}") from e
                        else:
                            if text_content.startswith("ping"):
                                await self._serializer.send_raw_text("pong")
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
            self._global_kill_flag.value = True
            raise
        finally:
            logger.info("Ending client message handler...")
