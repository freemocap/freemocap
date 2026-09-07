"""Explicit playback ranges, cancellation and failure isolation."""

import asyncio
import unittest
from unittest.mock import AsyncMock

from freemocap.core.playback.stream_session import PlaybackSession, PlaybackSource, PlaybackSink, PlaybackLimits, PlaybackRange, PlaybackEncoding


class PlaybackSessionTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self) -> PlaybackSession:
        self.source = AsyncMock(spec=PlaybackSource)
        self.source.read_group.return_value = b"pixels"
        self.sink = AsyncMock(spec=PlaybackSink)
        return PlaybackSession(source=self.source, sink=self.sink,
            limits=PlaybackLimits(frame_count=20, encoded_group_bytes=100))

    async def wait_end(self, count: int) -> None:
        async with asyncio.timeout(2.0):
            while self.sink.send_end.await_count < count:
                await asyncio.sleep(0)

    async def test_only_requested_ranges_are_sent_without_acknowledgments(self) -> None:
        session = self.make_session()
        task = asyncio.create_task(session.run())
        try:
            await asyncio.sleep(0)
            self.source.read_group.assert_not_awaited()
            session.request_range(PlaybackRange(encoding=PlaybackEncoding(scale=1.0, jpeg_quality=90), generation=1, start_frame=3, end_frame=15))
            await self.wait_end(1)
            await asyncio.sleep(0)
            self.assertEqual([call.kwargs['frame_number'] for call in self.source.read_group.await_args_list], list(range(3, 15)))
            session.request_range(PlaybackRange(encoding=PlaybackEncoding(scale=1.0, jpeg_quality=90), generation=2, start_frame=1, end_frame=2))
            await self.wait_end(2)
            self.assertEqual(self.source.read_group.await_args.kwargs['frame_number'], 1)
        finally:
            session.request_close()
            await task
        self.source.close.assert_awaited_once()

    async def test_cancel_drops_inflight_image_and_completes_range(self) -> None:
        session = self.make_session()
        started = asyncio.Event()
        release = asyncio.Event()

        async def read(*, frame_number: int, encoding: PlaybackEncoding) -> bytes:
            started.set()
            await release.wait()
            return b"pixels"

        self.source.read_group.side_effect = read
        session.request_range(PlaybackRange(encoding=PlaybackEncoding(scale=1.0, jpeg_quality=90), generation=1, start_frame=0, end_frame=20))
        task = asyncio.create_task(session.run())
        try:
            await asyncio.wait_for(started.wait(), timeout=2.0)
            session.cancel_range(generation=1)
            release.set()
            await self.wait_end(1)
            self.sink.send_group.assert_not_awaited()
            self.source.read_group.assert_awaited_once_with(frame_number=0, encoding=PlaybackEncoding(scale=1.0, jpeg_quality=90))
        finally:
            release.set()
            session.request_close()
            await task

    async def test_failure_closes_only_its_source(self) -> None:
        session = self.make_session()
        self.source.read_group.side_effect = RuntimeError('decoder failed')
        session.request_range(PlaybackRange(encoding=PlaybackEncoding(scale=1.0, jpeg_quality=90), generation=1, start_frame=0, end_frame=1))
        with self.assertRaisesRegex(RuntimeError, 'decoder failed'):
            await session.run()
        self.source.close.assert_awaited_once()

    async def test_invalid_range_and_oversize_payload_fail(self) -> None:
        session = self.make_session()
        for start, end in ((-1, 1), (2, 2), (0, 21)):
            with self.assertRaises(ValueError):
                session.request_range(PlaybackRange(encoding=PlaybackEncoding(scale=1.0, jpeg_quality=90), generation=1, start_frame=start, end_frame=end))
        self.source.read_group.return_value = b'x' * 101
        session.request_range(PlaybackRange(encoding=PlaybackEncoding(scale=1.0, jpeg_quality=90), generation=1, start_frame=0, end_frame=1))
        with self.assertRaisesRegex(ValueError, 'byte budget'):
            await session.run()
        self.source.close.assert_awaited_once()
