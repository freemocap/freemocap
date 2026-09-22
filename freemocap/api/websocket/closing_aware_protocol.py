"""Close the gap between transport shutdown and ASGI disconnect notification."""

from uvicorn._types import ASGISendEvent  # noqa: TC002 - required by runtime beartype checks
from uvicorn.protocols.utils import ClientDisconnected
from uvicorn.protocols.websockets.websockets_sansio_impl import WebSocketsSansIOProtocol


class ClosingAwareWebSocketProtocol(WebSocketsSansIOProtocol):
    """Reject writes once the socket starts closing, before connection_lost runs.

    Uvicorn 0.53's SansIO send checks only its delayed ``disconnected`` flag.
    Windows' transport can log and discard writes in that gap without raising.
    Keep this compatibility adapter until upstream handles closing transports.
    """

    async def send(self, message: ASGISendEvent) -> None:
        # Recheck after backpressure: the transport may close while we wait.
        await self.writable.wait()
        if self.transport.is_closing():
            raise ClientDisconnected()
        await super().send(message)
