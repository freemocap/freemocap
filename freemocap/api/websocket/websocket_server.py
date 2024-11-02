import asyncio
import logging
import multiprocessing
from typing import Optional

from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from skellycam.app.app_controller.app_controller import get_app_controller
from skellycam.app.app_state import AppStateDTO, AppState
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.timestamps.framerate_tracker import CurrentFrameRate
from skellycam.core.recorders.videos.video_recorder_manager import RecordingInfo
from skellycam.utilities.wait_functions import async_wait_1ms

logger = logging.getLogger(__name__)


class WebsocketServer:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.frontend_image_relay_task: Optional[asyncio.Task] = None
        self._app_state: AppState = get_app_controller().app_state

    async def __aenter__(self):
        logger.debug("Entering WebsocketRunner context manager...")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("WebsocketRunner context manager exiting...")
        if not self.websocket.client_state == WebSocketState.DISCONNECTED:
            await self.websocket.close()

    async def run(self):
        logger.info("Starting websocket runner...")
        try:
            await asyncio.gather(
                asyncio.create_task(self._frontend_image_relay()),
                asyncio.create_task(self._ipc_queue_relay()),
            )
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            raise

    async def _ipc_queue_relay(self):
        """
        Relay messages from the sub-processes to the frontend via the websocket.
        """
        logger.info("Starting websocket relay listener...")

        try:
            while True:
                if self._app_state.ipc_queue.qsize() > 0:
                    try:
                        await self._handle_ipc_queue_message(message=self._app_state.ipc_queue.get())
                    except multiprocessing.queues.Empty:
                        continue
                else:
                    await async_wait_1ms()

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending listener task...")
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Ending listener for frontend payload messages in queue...")
        logger.info("Ending listener for client messages...")

    async def _handle_ipc_queue_message(self, message: Optional[object] = None):
        if isinstance(message, AppStateDTO):
            logger.trace(f"Relaying AppStateDTO to frontend")

        elif isinstance(message, RecordingInfo):
            logger.trace(f"Relaying RecordingInfo to frontend")

        elif isinstance(message, CurrentFrameRate):
            logger.loop(f"Relaying CurrentFrameRate to frontend")
            self._app_state.current_framerate = message
        else:
            raise ValueError(f"Unknown message type: {type(message)}")

        await self.websocket.send_json(message.model_dump())

    async def _frontend_image_relay(self):
        """
        Relay image payloads from the shared memory to the frontend via the websocket.
        """
        logger.info(
            f"Starting frontend image payload relay...")
        mf_payload: Optional[MultiFramePayload] = None
        camera_group_uuid = None
        latest_mf_number = -1
        try:
            while True:
                await async_wait_1ms()

                if not self._app_state.shmorchestrator or not self._app_state.shmorchestrator.valid or not self._app_state.frame_escape_shm.ready_to_read:
                    latest_mf_number = -1
                    mf_payload = None
                    continue

                if self._app_state.camera_group and camera_group_uuid != self._app_state.camera_group.uuid:
                    latest_mf_number = -1
                    mf_payload = None
                    camera_group_uuid = self._app_state.camera_group.uuid
                    continue

                if not self._app_state.frame_escape_shm.latest_mf_number.value > latest_mf_number:
                    continue

                mf_payload = self._app_state.frame_escape_shm.get_multi_frame_payload(camera_configs=self._app_state.camera_group.camera_configs,
                                                                                      retrieve_type="latest")
                await self._send_frontend_payload(mf_payload)
                latest_mf_number = mf_payload.multi_frame_number

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending Frontend Image relay task...")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in image payload relay: {e.__class__}: {e}")
            raise

    async def _send_frontend_payload(self,
                                     mf_payload: MultiFramePayload):
        frontend_payload = FrontendFramePayload.from_multi_frame_payload(multi_frame_payload=mf_payload)
        logger.loop(f"Sending frontend payload through websocket...")
        if not self.websocket.client_state == WebSocketState.CONNECTED:
            logger.error("Websocket is not connected, cannot send payload!")
            raise RuntimeError("Websocket is not connected, cannot send payload!")

        await self.websocket.send_bytes(frontend_payload.model_dump_json().encode('utf-8'))

        if not self.websocket.client_state == WebSocketState.CONNECTED:
            logger.error("Websocket shut down while sending payload!")
            raise RuntimeError("Websocket shut down while sending payload!")
