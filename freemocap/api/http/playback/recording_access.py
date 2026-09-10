"""Keep a recording read lease through endpoint execution and response cleanup."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

import anyio
from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.types import Receive, Scope, Send

from freemocap.core.recording.recording_access import (
    RecordingAccess,
    RecordingBusyError,
)
from freemocap.system.default_paths import get_default_freemocap_recordings_path


class PlaybackResponse(Response):
    def __init__(self, *, response: Response) -> None:
        self.response = response

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await self.response(scope, receive, send)
        finally:
            if isinstance(self.response, StreamingResponse):
                iterator = self.response.body_iterator
                if not isinstance(iterator, AsyncGenerator):
                    raise TypeError(
                        "Playback streaming responses require a closeable async generator"
                    )
                with anyio.CancelScope(shield=True):
                    await iterator.aclose()


class RecordingPlaybackRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        handler = super().get_route_handler()

        async def handle_response(request: Request) -> Response:
            return PlaybackResponse(response=await handler(request))

        return handle_response

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope)
        recording_id = request.path_params.get("recording_id")
        if recording_id is not None:
            parent = Path(
                request.query_params.get("recording_parent_directory")
                or get_default_freemocap_recordings_path()
            )
            path = parent / recording_id
        elif self.path.endswith("/parquet") and "path" in request.query_params:
            path = Path(request.query_params["path"])
        else:
            await super().handle(scope, receive, send)
            return

        access: RecordingAccess = request.app.state.recording_access
        loop = asyncio.get_running_loop()
        # AnyIO's non-abandoning threadpool calls finish before the lease exits.
        with anyio.CancelScope() as cancellation:

            def cancel() -> None:
                loop.call_soon_threadsafe(cancellation.cancel)

            try:
                with access.read(path=path, cancel=cancel):
                    await super().handle(scope, receive, send)
            except RecordingBusyError as error:
                response = JSONResponse(
                    status_code=409,
                    content={
                        "code": "recording_busy",
                        "owner": error.owner.model_dump(mode="json"),
                    },
                )
                await response(scope, receive, send)
