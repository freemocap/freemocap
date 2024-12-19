import logging

from fastapi import APIRouter, WebSocket

from freemocap.api.websocket.websocket_server import FreemocapWebsocketServer

logger = logging.getLogger(__name__)

freemocap_websocket_router = APIRouter()


@freemocap_websocket_router.websocket("/connect")
async def freemocap_websocket_server_connect(websocket: WebSocket):
    """
    Websocket endpoint for client connection to the server - handles image data streaming to frontend.
    """

    await websocket.accept()
    logger.success(f"FreeMoCap Websocket connection established!")

    async with FreemocapWebsocketServer(websocket=websocket) as runner:
        await runner.run()
    logger.info("Websocket closed")
