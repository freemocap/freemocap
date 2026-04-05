"""
WebSocket server with settings sync integration.

Changes from original:
  - Accepts a SettingsManager and FreemocapApplication
  - Runs a _settings_state_relay task alongside existing tasks
  - _client_message_handler routes settings/* messages to settings_protocol
"""
import asyncio
import json
import logging

from fastapi import FastAPI
from skellycam.core.types.type_overloads import CameraIdString
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from freemocap.app.freemocap_application import FreemocapApplication, get_freemocap_app
from freemocap.app.settings_protocol import (
    handle_settings_message,
    settings_state_relay,
)
from freemocap.core.viz.frontend_payload import FrontendPayload
from freemocap.system.logging_configuration.handlers.websocket_log_queue_handler import (
    get_websocket_log_queue,
    MIN_LOG_LEVEL_FOR_WEBSOCKET,
)
from freemocap.utilities.wait_functions import await_10ms
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freemocap.app.settings import SettingsManager
    from skellycam.core.types.type_overloads import CameraGroupIdString
    from skellycam.core.recorders.framerate_tracker import FramerateTracker

logger = logging.getLogger(__name__)

BACKPRESSURE_WARNING_THRESHOLD: int = 100


class WebsocketServer:
    def __init__(self, fastapi_app: FastAPI, websocket: WebSocket):
        self.websocket = websocket
        if not hasattr(fastapi_app, "state") or not hasattr(fastapi_app.state, "global_kill_flag"):
            raise RuntimeError(
                "FastAPI app does not have a global_kill_flag in its state"
            )
        self._global_kill_flag = fastapi_app.state.global_kill_flag
        self._app: FreemocapApplication = get_freemocap_app()
        self._settings_manager: SettingsManager = self._app.settings_manager

        self._websocket_should_continue = True
        self.ws_tasks: list[asyncio.Task] = []
        self.last_received_frontend_confirmation: int = -1
        self.last_sent_frame_number: int = -1
        self._display_image_sizes: dict[CameraGroupIdString, dict[str, float]] | None = None
        self._frontend_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}
        # Serializes all WebSocket send operations to prevent concurrent-send
        # race conditions in the websockets legacy protocol (AssertionError in _drain_helper).
        self._send_lock = asyncio.Lock()

    async def __aenter__(self):
        logger.debug("Entering WebsocketRunner context manager...")
        self._websocket_should_continue = True
        # Sync settings from app state on connection
        self._settings_manager.update_from_app(self._app)
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
                self._client_message_handler(),
                name="WebsocketClientMessageHandler",
            ),
            asyncio.create_task(
                settings_state_relay(
                    websocket=self.websocket,
                    settings_manager=self._settings_manager,
                    should_continue=lambda: self.should_continue,
                    send_lock=self._send_lock,
                ),
                name="WebsocketSettingsStateRelay",
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

    def check_frame_acknowledgment_status(self) -> bool:
        if self.last_sent_frame_number == -1:
            return True
        return self.last_received_frontend_confirmation >= self.last_sent_frame_number

    async def _frontend_image_relay(self) -> None:
        """Relay image payloads from shared memory to the frontend via WebSocket."""
        logger.info("Starting frontend image payload relay...")
        try:
            skipped_previous = False
            while self.should_continue:
                await await_10ms()
                if self.check_frame_acknowledgment_status():
                    if skipped_previous:
                        skipped_previous = False
                    else:
                        try:
                            frontend_payloads = self._app.get_latest_frontend_payloads(
                                if_newer_than=self.last_sent_frame_number
                            )
                        except IndexError:
                            logger.warning(
                                f"Ring buffer overwrite detected (last_sent_frame_number={self.last_sent_frame_number}). "
                                f"Resetting to latest frame."
                            )
                            self.last_sent_frame_number = -1
                            continue

                        for pipeline_id, (payload_bytes, frontend_payload) in frontend_payloads.items():
                            frame_number = None
                            if not payload_bytes and not frontend_payload:
                                continue
                            if frontend_payload:
                                if not isinstance(frontend_payload, FrontendPayload):
                                    frame_number = frontend_payload
                                    frontend_payload = None
                                else:
                                    frame_number = frontend_payload.frame_number

                            if payload_bytes:
                                if not isinstance(payload_bytes, (bytes, bytearray)):
                                    raise TypeError(
                                        f"Invalid payload bytes on frame {frame_number} - "
                                        f"got type {type(payload_bytes).__name__}"
                                    )
                                async with self._send_lock:
                                    await self.websocket.send_bytes(payload_bytes)

                            if frontend_payload and frontend_payload.charuco_overlays:
                                async with self._send_lock:
                                    await self.websocket.send_json({
                                        camera_id: overlay_data.model_dump()
                                        for camera_id, overlay_data in frontend_payload.charuco_overlays.items()
                                    })

                            if frontend_payload and frontend_payload.mediapipe_overlays:
                                async with self._send_lock:
                                    await self.websocket.send_json({
                                        camera_id: overlay_data.model_dump()
                                        for camera_id, overlay_data in frontend_payload.mediapipe_overlays.items()
                                    })

                            if frontend_payload and frontend_payload.tracked_points3d:
                                points3d_dict = {
                                    point_name: tracked_point.model_dump()
                                    for point_name, tracked_point in frontend_payload.tracked_points3d.items()
                                }
                                async with self._send_lock:
                                    await self.websocket.send_json({"tracked_points3d": points3d_dict})

                            if frontend_payload and frontend_payload.rigid_body_poses:
                                rigid_body_dict = {
                                    bone_key: pose.model_dump()
                                    for bone_key, pose in frontend_payload.rigid_body_poses.items()
                                }
                                async with self._send_lock:
                                    await self.websocket.send_json({"rigid_body_poses": rigid_body_dict})

                            if frame_number is not None:
                                self.last_sent_frame_number = frame_number
                else:
                    skipped_previous = True
                    backpressure = self.last_sent_frame_number - self.last_received_frontend_confirmation
                    if (
                            backpressure > BACKPRESSURE_WARNING_THRESHOLD
                            and backpressure % BACKPRESSURE_WARNING_THRESHOLD == 0
                    ):
                        logger.trace(
                            f"Backpressure detected: {backpressure} frames not acknowledged by frontend! "
                            f"Last sent frame: {self.last_sent_frame_number}, "
                            f"last received confirmation: {self.last_received_frontend_confirmation}"
                        )

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
                        await self.websocket.send_json(log_entry)
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
                                if data_message_type.startswith("settings/"):
                                    handle_settings_message(
                                        data=data,
                                        settings_manager=self._settings_manager,
                                        app=self._app,
                                    )
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