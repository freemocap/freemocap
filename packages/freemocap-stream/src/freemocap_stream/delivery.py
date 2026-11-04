"""Deliver messages to WebSocket clients: newest wins, one writer per connection.

Frames and state snapshots replace one another, so a slow client should receive
fewer, newer messages rather than a growing backlog (FreeMoCap's frame relay
behaves the same way). `Latest` holds the newest encoded message of one stream.
Each `StreamConnection` follows any number of streams and sends through a single
lock, because WebSocket transports do not allow concurrent writes on one
connection.

Framework-agnostic: pass the connection's async send functions, such as aiohttp's
`ws.send_bytes` and `ws.send_str` or Starlette's `websocket.send_bytes` and
`websocket.send_text`. Use these objects on the event loop's thread; publish from
another thread with `loop.call_soon_threadsafe(latest.publish, message)`.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

SendBytes = Callable[[bytes], Awaitable[Any]]
SendText = Callable[[str], Awaitable[Any]]


class Latest:
    """The newest encoded message of one stream, numbered by publication."""

    def __init__(self) -> None:
        self._message: bytes | None = None
        self._version = 0
        self._published: asyncio.Future[None] | None = None

    @property
    def version(self) -> int:
        """How many messages have been published; 0 before the first."""
        return self._version

    @property
    def message(self) -> bytes | None:
        return self._message

    def publish(self, message: bytes) -> None:
        """Replace the newest message and wake every connection waiting for one."""
        self._message = message
        self._version += 1
        if self._published is not None and not self._published.done():
            self._published.set_result(None)
        self._published = None

    async def after(self, version: int) -> tuple[int, bytes]:
        """Wait until a message newer than `version` exists; return the newest one
        and its version. Messages published meanwhile are skipped."""
        while self._version <= version:
            if self._published is None:
                self._published = asyncio.get_running_loop().create_future()
            # Shielded: a connection that stops waiting must not cancel everyone's wake-up.
            await asyncio.shield(self._published)
        assert self._message is not None
        return self._version, self._message


class StreamConnection:
    """One client connection. Every send, binary or text, goes through one writer."""

    def __init__(self, send_bytes: SendBytes, send_text: SendText | None = None) -> None:
        self._send_bytes = send_bytes
        self._send_text = send_text
        self._writer = asyncio.Lock()

    async def send(self, message: bytes) -> None:
        async with self._writer:
            await self._send_bytes(message)

    async def send_text(self, text: str) -> None:
        if self._send_text is None:
            raise RuntimeError("This connection was created without a text sender")
        async with self._writer:
            await self._send_text(text)

    async def receive_text(self, text: str) -> str | None:
        """Handle a text message from the client. The client's heartbeat `ping` is
        answered with `pong`, and a `pong` needs nothing; any other text (such as
        FreeMoCap's display feedback) is returned for the application."""
        if text.startswith("ping"):
            await self.send_text("pong")
            return None
        if text == "pong":
            return None
        return text

    async def follow(self, *streams: Latest) -> None:
        """Send each stream's newest message, now and whenever it changes, until
        cancelled or a send fails (which is raised)."""
        followers = [asyncio.create_task(self._follow(stream)) for stream in streams]
        try:
            done, _ = await asyncio.wait(followers, return_when=asyncio.FIRST_EXCEPTION)
            for follower in done:
                follower.result()
        finally:
            for follower in followers:
                follower.cancel()
            await asyncio.gather(*followers, return_exceptions=True)

    async def _follow(self, stream: Latest) -> None:
        version = 0
        while True:
            version, message = await stream.after(version)
            await self.send(message)
