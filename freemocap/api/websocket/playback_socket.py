"""Isolated playback connection using shared CBOR and image payload machinery."""

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from enum import StrEnum

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from freemocap.api.http.playback.playback_router import _resolve_recording_path
from freemocap.core.playback.media_selection import PlaybackVideoSource, video_source_folder, discover_video_paths
from freemocap.api.websocket.send_serializer import SendSerializer
from freemocap.core.playback.stream_session import PlaybackSession, PlaybackLimits, PlaybackRange, PlaybackGroup, PlaybackEncoding
from freemocap.core.playback.video_source import NativeVideoSource, VideoSourceRequest
from freemocap.core.streaming.message_model import MessageEnvelope, encode_message

logger = logging.getLogger(__name__)
playback_socket_router = APIRouter(prefix="/websocket/playback", tags=["Playback"])


class PlaybackCommand(StrEnum):
    RANGE = "range"
    CANCEL = "cancel"
    CLOSE = "close"


class PlaybackEvent(StrEnum):
    READY = "playback_ready"
    FRAME = "playback_frame"
    END = "playback_end"
    FAILED = "playback_failed"


class SocketModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PlaybackOpen(SocketModel):
    source: PlaybackVideoSource
    encoded_group_bytes: int = Field(ge=1, le=128 * 1024 * 1024)


class ControlEnvelope(SocketModel):
    command: PlaybackCommand
    payload: dict[str, JsonValue]


class RangePayload(SocketModel):
    generation: int
    start_frame: int
    end_frame: int
    encoding: PlaybackEncoding


class CancelPayload(SocketModel):
    generation: int


@dataclass(frozen=True)
class PlaybackWireMessage:
    kind: PlaybackEvent
    envelope: MessageEnvelope = field(default_factory=MessageEnvelope)
    generation: int = 0
    frame_number: int | None = None
    image: bytes | None = None
    filenames: tuple[str, ...] | None = None
    frame_count: int | None = None
    decoded_group_bytes: int | None = None
    maximum_payload_bytes: int | None = None
    detail: str | None = None


class PlaybackSocketSink:
    def __init__(self, *, serializer: SendSerializer) -> None:
        self.serializer = serializer

    async def send_group(self, group: PlaybackGroup) -> None:
        if not self.serializer.is_connected:
            raise WebSocketDisconnect()
        await self.serializer.send_message(encode_message(PlaybackWireMessage(
            kind=PlaybackEvent.FRAME, generation=group.generation,
            frame_number=group.frame_number, image=group.payload)))

    async def send_end(self, *, generation: int) -> None:
        await self.serializer.send_message(encode_message(PlaybackWireMessage(kind=PlaybackEvent.END, generation=generation)))


async def receive_controls(*, websocket: WebSocket, session: PlaybackSession) -> None:
    while not session.closed:
        message = ControlEnvelope.model_validate_json(await websocket.receive_text())
        match message.command:
            case PlaybackCommand.RANGE:
                request = RangePayload.model_validate(message.payload)
                session.request_range(PlaybackRange(generation=request.generation,
                    start_frame=request.start_frame, end_frame=request.end_frame, encoding=request.encoding))
            case PlaybackCommand.CANCEL:
                request = CancelPayload.model_validate(message.payload)
                session.cancel_range(generation=request.generation)
            case PlaybackCommand.CLOSE:
                if message.payload:
                    raise ValueError("Close command does not accept payload fields")
                session.request_close()


@playback_socket_router.websocket("/{recording_id}")
async def playback_socket(websocket: WebSocket, recording_id: str, recording_parent_directory: str | None = None) -> None:
    await websocket.accept()
    serializer = SendSerializer(websocket)
    source: NativeVideoSource | None = None
    session: PlaybackSession | None = None
    producer: asyncio.Task[None] | None = None
    consumer: asyncio.Task[None] | None = None
    try:
        request = PlaybackOpen.model_validate_json(await websocket.receive_text())
        recording = _resolve_recording_path(recording_id, recording_parent_directory)
        folder = video_source_folder(recording=recording, source=request.source)
        paths = discover_video_paths(folder=folder)
        source = NativeVideoSource(request=VideoSourceRequest(paths=paths),
            registry=websocket.app.state.worker_registry)
        info = await source.prepare()
        session = PlaybackSession(source=source, sink=PlaybackSocketSink(serializer=serializer),
            limits=PlaybackLimits(frame_count=info.frame_count,
                encoded_group_bytes=min(request.encoded_group_bytes, max(65536, info.decoded_group_bytes))))
        await serializer.send_message(encode_message(PlaybackWireMessage(kind=PlaybackEvent.READY,
            filenames=info.filenames, frame_count=info.frame_count, decoded_group_bytes=info.decoded_group_bytes,
            maximum_payload_bytes=session.limits.encoded_group_bytes)))
        producer = asyncio.create_task(session.run())
        consumer = asyncio.create_task(receive_controls(websocket=websocket, session=session))
        done, _ = await asyncio.wait((producer, consumer), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except WebSocketDisconnect:
        pass
    except Exception as error:
        logger.exception("Playback session failed")
        if serializer.is_connected:
            await serializer.send_message(encode_message(PlaybackWireMessage(kind=PlaybackEvent.FAILED,
                detail=f"{type(error).__name__}: {error}")))
    finally:
        if session is not None:
            session.request_close()
        if consumer is not None:
            consumer.cancel()
            await asyncio.gather(consumer, return_exceptions=True)
        if producer is not None and not producer.done():
            producer.cancel()
            with suppress(asyncio.CancelledError):
                await producer
        elif source is not None:
            await source.close()
        if serializer.is_connected:
            await websocket.close()
