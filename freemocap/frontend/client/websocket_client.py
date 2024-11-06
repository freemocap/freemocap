import json
import logging
from typing import Union, Dict, Any

import websocket
from PySide6.QtWidgets import QWidget

from skellycam.app.app_state import AppStateDTO
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.recorders.timestamps.framerate_tracker import CurrentFrameRate
from skellycam.core.recorders.videos.video_recorder_manager import RecordingInfo

logger = logging.getLogger(__name__)

from PySide6.QtCore import QThread, Signal, Slot


class WebsocketThread(QThread):
    message_received = Signal(object)
    error_occurred = Signal(str)
    connection_opened = Signal()
    connection_closed = Signal()

    def __init__(self, websocket_url: str, parent=None):
        super().__init__(parent)
        self.websocket_url = websocket_url
        self.websocket = self._create_websocket()

    def _create_websocket(self):
        return websocket.WebSocketApp(
            self.websocket_url,
            on_message=self._on_message,
            on_open=self._on_open,
            on_error=self._on_error,
            on_close=self._on_close,
        )

    def run(self):
        self.websocket.run_forever(reconnect=True, ping_interval=5)

    def _on_open(self, ws):
        self.connection_opened.emit()

    def _on_message(self, ws, message):
        self.message_received.emit(message)

    def _on_error(self, ws, exception):
        self.error_occurred.emit(str(exception))

    def _on_close(self, ws, close_status_code, close_msg):
        self.connection_closed.emit()

class WebSocketClient(QWidget):
    new_frontend_payload_available = Signal(object)
    new_recording_info_available = Signal(object)
    new_app_state_available = Signal(object)
    new_framerate_info_available = Signal(object)

    def __init__(self,
                 base_url: str,
                 parent: QWidget):
        super().__init__(parent)
        self.websocket_url = base_url.replace("http", "ws") + "/websocket/connect"
        self.websocket_thread = WebsocketThread(self.websocket_url)

        # Connect signals
        self.websocket_thread.message_received.connect(self._handle_websocket_message)
        self.websocket_thread.error_occurred.connect(self._handle_error)
        self.websocket_thread.connection_opened.connect(self._on_open)
        self.websocket_thread.connection_closed.connect(self._on_close)


    def connect_websocket(self):
        self.websocket_thread.start()

    @Slot(str)
    def _handle_error(self, error_message: str):
        logger.exception(f"WebSocket exception: {error_message}")

    @Slot()
    def _on_open(self):
        logger.info(f"Connected to WebSocket at {self.websocket_url}")

    @Slot()
    def _on_close(self):
        logger.info(f"WebSocket connection closed, shutting down...")

    @Slot(str)
    def _handle_websocket_message(self, message: Union[str, bytes]):
        if isinstance(message, str):
            try:
                json_data = json.loads(message)
                self._handle_json_message(json_data)
            except json.JSONDecodeError:
                logger.info(f"Received text message: {message}")
        elif isinstance(message, bytes):
            logger.gui(f"Received binary message: size: {len(message) * .001:.3f}kB")
            self._handle_binary_message(message)

    def _handle_binary_message(self, message: bytes):
        try:
            payload = json.loads(message)
            self._process_payload(payload)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding binary message: {e}")

    def _handle_json_message(self, message: Dict[str, Any]):
        try:
            self._process_payload(message)
        except Exception as e:
            logger.exception(f"Error processing JSON message: {e}")

    def _process_payload(self, payload: Dict[str, Any]):
        if payload['type'] == FrontendFramePayload.__name__:
            fe_payload = FrontendFramePayload(**payload)
            logger.gui(f"Received FrontendFramePayload for cameras: {fe_payload.camera_ids}")
            self.new_frontend_payload_available.emit(fe_payload)
        elif payload['type'] == RecordingInfo.__name__:
            logger.gui(f"Received RecordingInfo object")
            self.new_recording_info_available.emit(RecordingInfo(**payload))
        elif payload['type'] == AppStateDTO.__name__:
            logger.gui(f"Received AppStateDTO object")
            self.new_app_state_available.emit(AppStateDTO(**payload))
        elif payload['type'] == CurrentFrameRate.__name__:
            logger.gui(f"Received CurrentFrameRate object")
            self.new_framerate_info_available.emit(CurrentFrameRate(**payload))
        else:
            logger.error(f"Received unrecognized payload")
            raise ValueError(f"Received unrecognized payload")

    def close(self):
        logger.info("Closing WebSocket client")
        if self.websocket_thread.isRunning():
            self.websocket_thread.quit()  # Gracefully stop the thread
            self.websocket_thread.wait()