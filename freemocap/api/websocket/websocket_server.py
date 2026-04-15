"""
WebSocket server with settings sync integration.
"""
import asyncio
import dataclasses
import json
import logging
import time
from typing import TYPE_CHECKING

import msgspec
import numpy as np
from fastapi import FastAPI
from skellycam.api.websocket.websocket_server import ServerFramerateCalculator
from skellylogs import get_websocket_log_queue
from skellylogs.handlers.websocket_log_queue_handler import MIN_LOG_LEVEL_FOR_WEBSOCKET
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from freemocap.api.websocket.websocket_message_types import WebsocketMessageType
from freemocap.app.freemocap_application import FreemocapApplication, get_freemocap_app

from freemocap.utilities.wait_functions import await_10ms
from skellycam.core.types.type_overloads import CameraGroupIdString, FrameNumberInt
from skellycam.core.recorders.framerate_tracker import FramerateTracker, CurrentFramerate

logger = logging.getLogger(__name__)

BACKPRESSURE_WARNING_THRESHOLD: int = 100


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
        self.last_sent_frame_number: FrameNumberInt = -1
        self._display_image_sizes: dict[CameraGroupIdString, dict[str, float]] | None = None
        self._frontend_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}

        self._server_framerate_calculators: dict[CameraGroupIdString, ServerFramerateCalculator] = {}
        self._display_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}
        self._last_framerate_send_time: float = 0.0

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

    async def run(self):
        logger.info("Starting websocket runner...")
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
                self._posthoc_progress_relay(),
                name="WebsocketPosthocProgressRelay",
            ),
            asyncio.create_task(
                self._client_message_handler(),
                name="WebsocketClientMessageHandler",
            ),
        ]

        try:
            await asyncio.gather(*self.ws_tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            for task in self.ws_tasks:
                if not task.done():
                    task.cancel()
            raise

    def last_frame_acknowledged(self) -> bool:
        if self.last_sent_frame_number == -1:
            return True
        return self.last_received_frontend_confirmation >= self.last_sent_frame_number

    async def _frontend_image_relay(self) -> None:
        logger.info("Starting frontend image payload relay...")
        try:
            skipped_previous = False
            while self.should_continue:
                await await_10ms()
                if not self.last_frame_acknowledged():
                    skipped_previous = True
                    backpressure = self.last_sent_frame_number - self.last_received_frontend_confirmation
                    if backpressure > BACKPRESSURE_WARNING_THRESHOLD and backpressure % BACKPRESSURE_WARNING_THRESHOLD == 0:
                        logger.trace(f"Backpressure: {backpressure} frames unacknowledged")
                    continue

                if skipped_previous:
                    skipped_previous = False
                    continue

                try:
                    packets, progress_updates = self._app.get_latest_frontend_payloads(if_newer_than=self.last_sent_frame_number)
                except IndexError:
                    logger.warning("Ring buffer overwrite — resetting to latest frame")
                    self.last_sent_frame_number = -1
                    continue

                for packet in packets:
                    if packet.frontend_payload is not None:
                        await self._send_msgspec_json(packet.frontend_payload)

                    if packet.image_bytes is not None:
                        async with self._send_lock:
                            await self.websocket.send_bytes(packet.image_bytes)

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

                if len(progress_updates) > 0:
                    for update_messages in progress_updates:
                        if len(update_messages) > 0:
                            for update_message in update_messages:
                                logger.trace(f"Sending {len(progress_updates)} updates through the websocket ")
                                await self._send_msgspec_json(update_message)

                # Send framerate updates from our local trackers (throttled to ~4Hz)
                now = time.monotonic()
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

    async def _logs_relay(self, ws_log_level: int = MIN_LOG_LEVEL_FOR_WEBSOCKET):
        logger.info("Starting websocket log relay listener...")
        logs_queue = get_websocket_log_queue()
        try:
            while self.should_continue:
                if not logs_queue.empty() and self.websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        # Skellycam's WebSocketQueueHandler puts LogRecordModel dicts
                        # into the queue via put_nowait(). On rare occasions a child
                        # process exit (cancel_join_thread) can leave a partial pickle
                        # in the pipe — the except below handles that gracefully.
                        log_entry: dict = logs_queue.get_nowait()
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

    async def _posthoc_progress_relay(self) -> None:
        logger.info("Starting posthoc progress relay...")
        progress_queue = self._app.posthoc_pipeline_manager.shared_progress_queue
        try:
            while self.should_continue:
                if not progress_queue.empty() and self.websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        msg = progress_queue.get_nowait()
                    except Exception:
                        continue
                    payload = {
                        "message_type": WebsocketMessageType.POSTHOC_PROGRESS,
                        "pipeline_id": msg.pipeline_id,
                        "phase": msg.phase,
                        "progress_fraction": msg.progress_fraction,
                        "detail": msg.detail,
                    }
                    await self._send_msgspec_json(payload)
                else:
                    await await_10ms()
        except asyncio.CancelledError:
            logger.debug("Posthoc progress relay task cancelled")
        except WebSocketDisconnect:
            logger.info("Client disconnected, ending posthoc progress relay task...")
        except Exception as e:
            logger.exception(
                f"Error in posthoc progress relay: {e.__class__.__name__}: {e}"
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

                                if "frameNumber" in data:
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
