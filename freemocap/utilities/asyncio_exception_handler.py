import asyncio
import logging

logger = logging.getLogger(__name__)


def suppress_proactor_connection_reset(loop: asyncio.AbstractEventLoop) -> None:
    """Silence noisy ConnectionResetError callbacks on Windows proactor loop.

    On Windows, remote TCP resets after HTTP responses / WebSocket close can
    cause ``_ProactorBasePipeTransport._call_connection_lost`` to fire a
    ``ConnectionResetError`` during transport cleanup. The data was already
    delivered — this is purely transport-layer noise.
    """
    default_handler = loop.get_exception_handler()

    def handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        msg = context.get("message", "")
        exc = context.get("exception")
        if isinstance(exc, ConnectionResetError):
            return
        if "connection_lost" in str(msg).lower():
            return
        if default_handler is not None:
            default_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(handler)
    logger.debug("Registered proactor ConnectionResetError suppressor on event loop")
