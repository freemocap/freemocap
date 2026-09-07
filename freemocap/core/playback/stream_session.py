"""Client-requested multiframe ranges, independent of live-camera scheduling."""

import asyncio
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class PlaybackEncoding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    scale: float = Field(gt=0.0, le=1.0)
    jpeg_quality: int = Field(ge=1, le=100)


@dataclass(frozen=True)
class PlaybackLimits:
    frame_count: int
    encoded_group_bytes: int

    def __post_init__(self) -> None:
        if min(self.frame_count, self.encoded_group_bytes) <= 0:
            raise ValueError("Playback limits must be positive")


@dataclass(frozen=True)
class PlaybackRange:
    generation: int
    start_frame: int
    end_frame: int
    encoding: PlaybackEncoding


@dataclass(frozen=True)
class PlaybackGroup:
    generation: int
    frame_number: int
    payload: bytes


@runtime_checkable
class PlaybackSource(Protocol):
    async def read_group(self, *, frame_number: int, encoding: PlaybackEncoding) -> bytes: ...
    async def close(self) -> None: ...


@runtime_checkable
class PlaybackSink(Protocol):
    async def send_group(self, group: PlaybackGroup) -> None: ...
    async def send_end(self, *, generation: int) -> None: ...


class PlaybackSession:
    """Fulfill exactly the requested half-open range, then wait for the client."""

    def __init__(self, *, source: PlaybackSource, sink: PlaybackSink, limits: PlaybackLimits) -> None:
        self.source = source
        self.sink = sink
        self.limits = limits
        self.generation = 0
        self.next_frame = 0
        self.end_frame = 0
        self.request: PlaybackRange | None = None
        self.cancelled = False
        self.closed = False
        self.running = False
        self.changed = asyncio.Event()

    def request_range(self, request: PlaybackRange) -> None:
        if self.closed:
            raise RuntimeError("Playback session is closed")
        if request.generation != self.generation + 1:
            raise ValueError("Range generation must advance exactly once")
        if not 0 <= request.start_frame < request.end_frame <= self.limits.frame_count:
            raise ValueError("Requested range is outside the recording")
        self.request = request
        self.generation = request.generation
        self.next_frame = request.start_frame
        self.end_frame = request.end_frame
        self.cancelled = False
        self.changed.set()

    def cancel_range(self, *, generation: int) -> None:
        if generation != self.generation:
            raise ValueError("Cancellation must identify the current range")
        self.cancelled = True
        self.changed.set()

    def request_close(self) -> None:
        self.closed = True
        self.changed.set()

    async def run(self) -> None:
        if self.running or self.closed:
            raise RuntimeError("Playback session cannot be restarted")
        self.running = True
        completed_generation = 0
        try:
            while not self.closed:
                if self.cancelled or self.next_frame >= self.end_frame:
                    if completed_generation != self.generation:
                        completed_generation = self.generation
                        await self.sink.send_end(generation=self.generation)
                        continue
                    self.changed.clear()
                    await self.changed.wait()
                    continue
                generation = self.generation
                number = self.next_frame
                if self.request is None:
                    raise RuntimeError("Playback range has no encoding request")
                payload = await self.source.read_group(frame_number=number, encoding=self.request.encoding)
                if self.closed or self.cancelled or generation != self.generation:
                    continue
                if not payload or len(payload) > self.limits.encoded_group_bytes:
                    raise ValueError("Encoded multiframe is empty or exceeds its byte budget")
                self.next_frame = number + 1
                await self.sink.send_group(PlaybackGroup(generation=generation, frame_number=number, payload=payload))
        finally:
            self.closed = True
            await self.source.close()
