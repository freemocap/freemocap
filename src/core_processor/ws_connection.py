import logging

import websockets
from orjson import orjson

from src.core_processor.app_events.app_queue import AppQueue

logger = logging.getLogger(__name__)


class WSConnection:

    _host = "ws://localhost:8080/ws"

    async def connect(self, webcam_id: str):
        # TODO: Spawn new process to perform this job?
        uri = f"{self._host}/{webcam_id}"
        app = AppQueue()
        app.create(webcam_id)
        queue = app.get_by_webcam_id(webcam_id)
        async for websocket in websockets.connect(uri, max_size=None, ping_timeout=None):
            try:
                async for message in websocket:
                    # How expensive is it to parse a json string?
                    asJson = orjson.loads(message)
                    await queue.put(asJson)
                    print(f"webcam_id: {webcam_id}, msg rcv")
            except websockets.ConnectionClosed as e:
                logger.error(e)
                continue
