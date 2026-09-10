import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from freemocap.api.websocket.websocket_server import WebsocketServer

logger = logging.getLogger(__name__)

websocket_router = APIRouter(tags=["Websocket"], prefix="/websocket")


@websocket_router.websocket("/connect")
async def websocket_server_connect(websocket: WebSocket) -> None:
    app = websocket.scope["app"]
    if app.state.global_kill_flag.value:
        await websocket.close(code=1011, reason="Server shutting down")
        return
    await websocket.accept()
    try:
        async with WebsocketServer(websocket=websocket,
                                   fastapi_app=app) as websocket_server:
            logger.info("Websocket initialized at url: %s", websocket.url)
            await websocket_server.run()
    except WebSocketDisconnect:
        logger.info("Websocket client disconnected: %s", websocket.url)
    except Exception as error:
        app.state.fatal_error = error
        app.state.global_kill_flag.value = True
        logger.exception("Fatal WebSocket failure; shutting down server")
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close(code=1011, reason="Fatal server error; see server log")
        raise
    finally:
        logger.info("Websocket closed at url: %s", websocket.url)
