import asyncio
import logging
import multiprocessing
from typing import Optional

from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.timestamps.framerate_tracker import CurrentFrameRate
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.skellycam_app.skellycam_app_state import SkellycamAppStateDTO
from skellycam.utilities.wait_functions import async_wait_1ms
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from freemocap.freemocap_app.freemocap_app_state import get_freemocap_app_state, FreemocapAppState
from freemocap.pipelines.dummy_pipeline import DummyProcessingServer
from freemocap.pipelines.pipeline_abcs import ReadTypes, BaseProcessingServer

logger = logging.getLogger(__name__)


class FreemocapWebsocketServer:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self._freemocap_app_state: FreemocapAppState = get_freemocap_app_state()
        self.frontend_image_relay_task: Optional[asyncio.Task] = None

    async def __aenter__(self):
        logger.debug("Entering FreeMoCap  WebsocketServer context manager...")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug(" FreeMoCap  WebsocketServer context manager exiting...")
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
                if self._freemocap_app_state.skellycam_ipc_queue.qsize() > 0:
                    try:
                        await self._handle_ipc_queue_message(
                            message=self._freemocap_app_state.skellycam_ipc_queue.get())
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
        if isinstance(message, FreemocapAppState) or isinstance(message, SkellycamAppStateDTO):
            logger.trace(f"Relaying AppStateDTO to frontend")

        elif isinstance(message, RecordingInfo):
            logger.trace(f"Relaying RecordingInfo to frontend")

        elif isinstance(message, CurrentFrameRate):
            logger.loop(f"Relaying CurrentFrameRate to frontend")
            self._freemocap_app_state.skellycam_app_state.current_framerate = message
        else:
            raise ValueError(f"Unknown message type: {type(message)}")

        await self.websocket.send_json(message.model_dump())

    async def _frontend_image_relay(self):
        """
        Relay image payloads from the shared memory to the frontend via the websocket.
        """
        logger.info(
            f"Starting frontend image payload relay...")

        camera_group_uuid = None
        latest_mf_number = -1
        processing_server: BaseProcessingServer|None = None #Starts when camera group is detected, should probably be handled differently but this works fn
        try:
            while True:
                await async_wait_1ms()
                # TODO - clean this up once the architecture firms up, names too long
                if not self._freemocap_app_state.skellycam_app_state.camera_group:
                    latest_mf_number = -1
                    continue

                if (not self._freemocap_app_state.skellycam_app_state.shmorchestrator or
                        not self._freemocap_app_state.skellycam_app_state.shmorchestrator.valid or
                        not self._freemocap_app_state.skellycam_app_state.frame_escape_shm.ready_to_read):
                    latest_mf_number = -1
                    continue

                if self._freemocap_app_state.skellycam_app_state.camera_group and camera_group_uuid != self._freemocap_app_state.skellycam_app_state.camera_group.uuid:
                    latest_mf_number = -1
                    camera_group_uuid = self._freemocap_app_state.skellycam_app_state.camera_group.uuid
                    if processing_server:
                        processing_server.shutdown_pipeline()
                    processing_server = self._freemocap_app_state.create_processing_server()

                    processing_server.start()
                    continue

                if not self._freemocap_app_state.skellycam_app_state.frame_escape_shm.latest_mf_number.value > latest_mf_number:
                    continue

                mf_payload: MultiFramePayload = self._freemocap_app_state.skellycam_app_state.frame_escape_shm.get_multi_frame_payload(
                    camera_configs=self._freemocap_app_state.camera_configs,
                    retrieve_type=ReadTypes.LATEST.value)


                if processing_server:
                    processing_server.intake_data(mf_payload)
                    mf_payload = processing_server.annotate_images(mf_payload)

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

