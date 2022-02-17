import logging
import websockets
from orjson import orjson

logger = logging.getLogger(__name__)


class WSConnection:

    _host = "ws://localhost:8080/ws"

    async def connect(self, webcam_id: str, queue):
        uri = f"{self._host}/{webcam_id}"
        async for websocket in websockets.connect(uri, max_size=None, ping_timeout=None):
            try:
                async for message in websocket:
                    # How expensive is it to parse a json string?
                    as_json = orjson.loads(message)
                    logger.info(f"webcam_id: {webcam_id}, msg rcv")
                    queue.put(as_json, timeout=1)
            except websockets.ConnectionClosed as e:
                logger.error(e)
                continue
