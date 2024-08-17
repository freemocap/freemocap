import asyncio
import json
from typing import Union, Dict, Any

import websockets

import logging
logger = logging.getLogger(__name__)


class WebSocketClient:
    def __init__(self, base_url: str):
        self.websocket_url = base_url.replace("http", "ws") + "/ws/connect"
        self.loop = asyncio.get_event_loop()

    async def _ws_connect(self) -> None:
        async with websockets.connect(self.websocket_url) as websocket:
            logger.info(f"Connected to WebSocket at {self.websocket_url}")
            try:
                while True:
                    message = await websocket.recv()
                    self._handle_websocket_message(message)
            except websockets.ConnectionClosed:
                logger.info("WebSocket connection closed")

    def _handle_websocket_message(self, message: Union[str, bytes]) -> None:
        if isinstance(message, str):
            try:
                json_data = json.loads(message)
                logger.info(f"Received JSON message: {json_data}")
                self._handle_json_message(json_data)
            except json.JSONDecodeError:
                logger.info(f"Received text message: {message}")
                self._handle_text_message(message)
        elif isinstance(message, bytes):
            logger.info(f"Received binary message of length {len(message)}")
            self._handle_binary_message(message)

    def _handle_text_message(self, message: str) -> None:
        # Add your text message handling logic here
        pass

    def _handle_binary_message(self, message: bytes) -> None:
        # Add your binary message handling logic here
        pass

    def _handle_json_message(self, message: Dict[str, Any]) -> None:
        # Add your JSON message handling logic here
        pass

    def start_websocket(self) -> None:
        self.loop.run_until_complete(self._ws_connect())

    def close(self) -> None:
        logger.info("Closing WebSocket client")
        self.loop.stop()
