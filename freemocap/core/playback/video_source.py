"""Managed native decoding feeding the shared synchronized image encoder."""

import asyncio
import multiprocessing
from concurrent.futures import Future
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from threading import Lock

from freemocap.core.playback.stream_session import PlaybackEncoding

import cv2
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.sequential_video_reader import SequentialVideoReader, VideoFileIdentity
from skellycam.core.recorders.videos.video_file_metadata import VideoFileMetadata
from skellycam.core.types.frontend_payload_bytearray import ImagePayloadFrame, ImagePayloadRequest, encode_image_payload


@dataclass(frozen=True)
class VideoSourceRequest:
    paths: tuple[Path, ...]

    def __post_init__(self) -> None:
        if not self.paths or len(set(self.paths)) != len(self.paths):
            raise ValueError("Playback requires distinct video paths")


@dataclass(frozen=True)
class VideoSourceInfo:
    frame_count: int
    decoded_group_bytes: int
    filenames: tuple[str, ...]


@dataclass
class ReadGroup:
    frame_number: int
    encoding: PlaybackEncoding
    result: Future[bytes] = field(default_factory=Future)


class NativeVideoSource:
    def __init__(self, *, request: VideoSourceRequest, registry: WorkerRegistry) -> None:
        self.request = request
        self.registry = registry
        self.shutdown = multiprocessing.Value("b", False)
        self.commands: Queue[ReadGroup] = Queue(maxsize=1)
        self.ready: Future[VideoSourceInfo] = Future()
        self.failure: BaseException | None = None
        self.submission_lock = Lock()
        self.stopped = False
        self.worker = registry.create_worker(shutdown_flag=self.shutdown, worker_mode=WorkerMode.THREAD,
            target=self._run, name="PlaybackVideoReader")
        self.worker.start()

    async def prepare(self) -> VideoSourceInfo:
        return await asyncio.shield(asyncio.wrap_future(self.ready))

    async def read_group(self, *, frame_number: int, encoding: PlaybackEncoding) -> bytes:
        command = ReadGroup(frame_number=frame_number, encoding=encoding)
        with self.submission_lock:
            if self.failure is not None:
                raise self.failure
            if self.stopped or self.shutdown.value or not self.worker.is_alive():
                raise RuntimeError("Playback reader is closed")
            self.commands.put_nowait(command)
        return await asyncio.shield(asyncio.wrap_future(command.result))

    async def close(self) -> None:
        self.worker.mark_stopping()
        self.shutdown.value = True
        await asyncio.to_thread(self.worker.join, timeout=10.0)
        if self.worker.is_alive():
            raise RuntimeError("Playback native reader did not finish shutdown")

    def _run(self) -> None:
        command: ReadGroup | None = None
        try:
            with ExitStack() as cleanup:
                identities = tuple(VideoFileIdentity.from_path(path=path) for path in self.request.paths)
                metadata = tuple(VideoFileMetadata.from_path(path=path) for path in self.request.paths)
                counts = {video.reported_frame_count for video in metadata}
                if len(counts) != 1:
                    raise ValueError("Synchronized playback requires equal video frame counts")
                count = next(iter(counts))
                readers: list[SequentialVideoReader] = []
                for path in self.request.paths:
                    reader = SequentialVideoReader(path=path)
                    cleanup.callback(reader.close)
                    readers.append(reader)
                self.ready.set_result(VideoSourceInfo(frame_count=count,
                    decoded_group_bytes=sum(video.width * video.height * 4 for video in metadata),
                    filenames=tuple(path.name for path in self.request.paths)))
                while not self.shutdown.value:
                    try:
                        command = self.commands.get(timeout=0.05)
                    except Empty:
                        continue
                    if not 0 <= command.frame_number < count:
                        raise ValueError("Playback frame is outside the recording")
                    frames: list[ImagePayloadFrame] = []
                    for index, (reader, identity) in enumerate(zip(readers, identities, strict=True)):
                        if VideoFileIdentity.from_path(path=reader.path) != identity:
                            raise RuntimeError(f"Video changed during playback: {reader.path}")
                        pixels = reader.read_bgr(frame_number=command.frame_number)
                        frames.append(ImagePayloadFrame(transport_id=f"view{index}", transport_index=index,
                            frame_number=command.frame_number, timestamp=command.frame_number / metadata[0].reported_fps,
                            image=pixels, output_width=max(1, int(pixels.shape[1] * command.encoding.scale)),
                            output_height=max(1, int(pixels.shape[0] * command.encoding.scale))))
                    if command.frame_number == count - 1:
                        for reader in readers:
                            try:
                                reader.read_bgr(frame_number=count)
                            except IndexError:
                                continue
                            raise ValueError(f"Video contains more frames than reported: {reader.path}")
                    _, _, payload = encode_image_payload(ImagePayloadRequest(frames=tuple(frames),
                        jpeg_encoding_parameters=(cv2.IMWRITE_JPEG_QUALITY, command.encoding.jpeg_quality)))
                    command.result.set_result(bytes(payload))
                    command = None
        except BaseException as error:
            self.failure = error
            self.shutdown.value = True
            if not self.ready.done():
                self.ready.set_exception(error)
            if command is not None and not command.result.done():
                command.result.set_exception(error)
            raise
        finally:
            with self.submission_lock:
                self.stopped = True
            while True:
                try:
                    pending = self.commands.get_nowait()
                except Empty:
                    break
                pending.result.set_exception(RuntimeError("Playback reader stopped"))
