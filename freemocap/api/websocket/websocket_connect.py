import logging

from fastapi import APIRouter, WebSocket

from freemocap.api.websocket.websocket_server import WebsocketServer

logger = logging.getLogger(__name__)

websocket_router = APIRouter(tags=["Websocket"], prefix="/websocket")


@websocket_router.websocket("/connect")
async def websocket_server_connect(websocket: WebSocket):
    await websocket.accept()
    app = websocket.scope["app"]
    logger.success(f"Websocket connection established at url: {websocket.url}")
    async with WebsocketServer(websocket=websocket,
                               fast_api_app=app) as websocket_server:
        await websocket_server.run()
    logger.info("Websocket closed")
