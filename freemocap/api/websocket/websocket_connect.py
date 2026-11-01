import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from freemocap.api.websocket.websocket_server import WebsocketServer
from freemocap.api.websocket.client_messages import ClientMessageError

logger = logging.getLogger(__name__)

websocket_router = APIRouter(tags=["Websocket"], prefix="/websocket")


@websocket_router.websocket("/connect")
async def websocket_server_connect(websocket: WebSocket) -> None:
    app = websocket.scope["app"]
    if app.state.global_kill_flag.value:
        await websocket.close(code=1011, reason="Server shutting down")
        return
    try:
        await websocket.accept()
        async with WebsocketServer(websocket=websocket,
                                   fastapi_app=app) as websocket_server:
            logger.info("Websocket initialized at url: %s", websocket.url)
            await websocket_server.run()
    except WebSocketDisconnect:
        logger.info("Websocket client disconnected: %s", websocket.url)
    except Exception as error:
        invalid_input = isinstance(error, ClientMessageError)
        if invalid_input:
            logger.warning("Closing WebSocket with invalid client input: %s", websocket.url)
        else:
            logger.exception("WebSocket connection failed: %s", websocket.url)
        if websocket.application_state == WebSocketState.CONNECTED:
            try:
                await websocket.close(code=1008 if invalid_input else 1011,
                                      reason="Invalid client message" if invalid_input else "Connection failed; see server log")
            except (WebSocketDisconnect, RuntimeError, OSError):
                logger.debug("WebSocket transport already closed")
    finally:
        logger.info("Websocket closed at url: %s", websocket.url)
