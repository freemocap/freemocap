import asyncio
import json
import logging

from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect
from fastapi import FastAPI

from skellycam.core.camera_group.camera_group_manager import CameraGroupManager, get_or_create_camera_group_manager
from skellycam.core.recorders.framerate_tracker import FramerateTracker, CurrentFramerate
from skellycam.core.types.type_overloads import CameraGroupIdString, FrameNumberInt, MultiframeTimestampFloat

from freemocap.core.tasks.frontend_payload_builder.frontend_payload import FrontendPayload
from freemocap.freemocap_app.freemocap_application import FreemocApp, get_freemocap_app
from freemocap.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue, MIN_LOG_LEVEL_FOR_WEBSOCKET
from freemocap.utilities.wait_functions import await_10ms

logger = logging.getLogger(__name__)

BACKPRESSURE_WARNING_THRESHOLD: int = 100  # Number of frames before we warn about backpressure


class WebsocketServer:
    def __init__(self, fast_api_app: FastAPI, websocket: WebSocket):

        self.websocket = websocket
        if not hasattr(fast_api_app, "state") or not hasattr(fast_api_app.state, "global_kill_flag"):
            raise RuntimeError("FastAPI app does not have a global_kill_flag in its state - define those fields when creating fastapi app")
        self._global_kill_flag = fast_api_app.state.global_kill_flag
        self._app: FreemocApp = get_freemocap_app()

        self._websocket_should_continue = True
        self.ws_tasks: list[asyncio.Task] = []
        self.last_received_frontend_confirmation: int = -1
        self.last_sent_frame_number: int = -1
        self._display_image_sizes: dict[CameraGroupIdString, dict[str, float]] | None = None
        self._frontend_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}

    async def __aenter__(self):
        logger.debug("Entering WebsocketRunner context manager...")
        self._websocket_should_continue = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("WebsocketRunner context manager exiting...")
        self._websocket_should_continue = False

        # Only close if still connected
        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.close()
        # Cancel all tasks
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
        self.ws_tasks = [asyncio.create_task(self._frontend_image_relay(), name="WebsocketFrontendImageRelay"),
                         asyncio.create_task(self._logs_relay(), name="WebsocketLogsRelay"),
                         asyncio.create_task(self._client_message_handler(), name="WebsocketClientMessageHandler")]

        try:
            await asyncio.gather(*self.ws_tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            # Cancel all tasks when exiting
            for task in self.ws_tasks:
                if not task.done():
                    task.cancel()
            raise

    def check_frame_acknowledgment_status(self) -> bool:
        if self.last_sent_frame_number == -1:
            return True
        return self.last_received_frontend_confirmation >= self.last_sent_frame_number

    async def _frontend_image_relay(self):
        """
        Relay image payloads from the shared memory to the frontend via the websocket.
        """
        logger.info(
            f"Starting frontend image payload relay...")
        try:
            skipped_previous = False
            while self.should_continue:
                await await_10ms()
                if self.check_frame_acknowledgment_status():
                    if skipped_previous:  # skip an extra frame if there was backpressure from frontend
                        skipped_previous = False
                    else:
                        new_frontend_payloads: dict[
                            CameraGroupIdString, FrontendPayload] = self._app.get_latest_frontend_payloads(
                            if_newer_than=self.last_sent_frame_number)

                        for pipeline_id, (frontend_payload, images_bytearray)  in new_frontend_payloads.items():
                            await self.websocket.send_bytes(images_bytearray)
                            self.last_sent_frame_number = frontend_payload.frame_number
                            if pipeline_id not in self._frontend_framerate_trackers:
                                self._frontend_framerate_trackers[pipeline_id] = FramerateTracker.create(
                                    framerate_source=f"Frontend-{pipeline_id}")
                            # self._frontend_framerate_trackers[pipeline_id].update(multiframe_timestamp)
                else:
                    skipped_previous = True
                    backpressure = self.last_sent_frame_number - self.last_received_frontend_confirmation
                    if backpressure > BACKPRESSURE_WARNING_THRESHOLD and backpressure % BACKPRESSURE_WARNING_THRESHOLD == 0:
                        logger.trace(
                            f"Backpressure detected: {backpressure} frames not acknowledged by frontend! Last sent frame: {self.last_sent_frame_number}, last received confirmation: {self.last_received_frontend_confirmation}")

                # backend_framerate_updates: dict[
                #     CameraGroupIdString, CurrentFramerate] = self._app.get_backend_framerate_updates()
                # if backend_framerate_updates:
                #     for camera_group_id, backend_framerate in backend_framerate_updates.items():
                #         if camera_group_id not in self._frontend_framerate_trackers:
                #             continue
                #         framerate_message = {
                #             "message_type": "framerate_update",
                #             "camera_group_id": camera_group_id,
                #             "backend_framerate": backend_framerate.model_dump(),
                #             "frontend_framerate": self._frontend_framerate_trackers[
                #                 camera_group_id].current_framerate.model_dump()
                #         }
                #         await self.websocket.send_json(framerate_message)

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending Frontend Image relay task...")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in image payload relay: {e.__class__}: {e}")
            self._global_kill_flag.value = True
            raise

    async def _logs_relay(self, ws_log_level: int = MIN_LOG_LEVEL_FOR_WEBSOCKET):
        logger.info("Starting websocket log relay listener...")
        logs_queue = get_websocket_log_queue()
        try:
            while self.should_continue:
                if not logs_queue.empty() and self.websocket.client_state == WebSocketState.CONNECTED:
                    log_record: logging.LogRecord = logs_queue.get_nowait()
                    if log_record.levelno < ws_log_level:
                        continue  # Skip logs below the specified level

                    # if traceback is present, replace with string
                    if log_record.exc_info:
                        log_record.exc_text = logging.Formatter().formatException(log_record.exc_info)
                        log_record.exc_info = None
                    await self.websocket.send_json(log_record)
                else:
                    await await_10ms()
        except asyncio.CancelledError:
            logger.debug("Log relay task cancelled")
        except WebSocketDisconnect:
            logger.info("Client disconnected, ending log relay task...")
        except Exception as e:
            logger.exception(f"Error in websocket log relay: {e.__class__}: {e}")
            self._global_kill_flag.value = True
            raise

    async def _client_message_handler(self):
        """
        Handle messages from the client.
        """
        logger.info("Starting client message handler...")
        try:
            while self.should_continue:
                message = await self.websocket.receive()
                if message:
                    if "text" in message:
                        text_content = message.get("text", "")
                        # Try to parse as JSON if it looks like JSON
                        if text_content.strip().startswith('{') or text_content.strip().startswith('['):
                            try:
                                data = json.loads(text_content)
                                # Handle received_frame acknowledgment
                                if 'frameNumber' in data:
                                    self.last_received_frontend_confirmation = data['frameNumber']
                                    self._display_image_sizes = data.get('displayImageSizes', None)


                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to decode JSON message: {e}")
                        else:
                            # Handle plain text messages
                            if text_content.startswith("ping"):
                                await self.websocket.send_text("pong")
                            elif text_content.startswith("pong"):
                                pass
                            else:
                                logger.info(f"Websocket received message: `{text_content}`")
                    elif "websocket" in message:
                        logger.trace(f"Received unknown websocket control message: {message}")
                    else:
                        logger.warning(f"Received unexpected message format: {message}")

        except asyncio.CancelledError:
            logger.debug("Client message handler task cancelled")
        except Exception as e:
            logger.exception(f"Error handling client message: {e.__class__}: {e}")
            self._global_kill_flag.value = True
            raise
        finally:
            logger.info("Ending client message handler...")
