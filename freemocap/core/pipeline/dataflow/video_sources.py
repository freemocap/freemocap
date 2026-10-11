"""Validated recording sources and bounded, independently advancing video readers.

This thread-only adapter yields owned image arrays directly to a backend consumer.
It does not publish pixels through pubsub or implement shared-memory fan-out.
"""
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from multiprocessing.sharedctypes import Synchronized
from queue import Empty, Full, Queue
from threading import Event
from time import perf_counter
from collections import deque

import numpy as np
from numpy.typing import NDArray
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.sequential_video_reader import SequentialVideoReader
from skellycam.core.timestamps.recording_timing_reader import RecordingTiming

from freemocap.core.pipeline.dataflow.camera_join import CameraFrameKey, ProducerOutcome
from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper, VideoMetadata
from freemocap.core.reconstruction.recording_timing import RecordingGroupTiming
from freemocap.core.recording.result_processing.observation_inputs import camera_group_name


@dataclass(frozen=True)
class CameraVideoSource:
    camera_id: str
    video_metadata: VideoMetadata
    camera_timing: RecordingTiming


@dataclass(frozen=True)
class RecordingVideoSources:
    recording_path: Path
    sensor_group: str
    camera_sources: tuple[CameraVideoSource, ...]
    group_timing: RecordingTiming

    def __post_init__(self) -> None:
        cameras = tuple(source.camera_id for source in self.camera_sources)
        if not cameras or len(set(cameras)) != len(cameras):
            raise ValueError("Recording sources require unique camera identities")
        counts = {source.video_metadata.frame_count for source in self.camera_sources}
        if len(counts) != 1 or next(iter(counts)) <= 0:
            raise ValueError("Recording sources require equal positive frame counts")
        for source in self.camera_sources:
            video = source.video_metadata
            if video.start_frame != 0 or video.end_frame != video.frame_count:
                raise ValueError("This source adapter currently requires full-video coverage")
            if len(source.camera_timing.timestamps_s) != video.frame_count:
                raise ValueError("Camera timing must cover every declared frame")
        if len(self.group_timing.timestamps_s) != next(iter(counts)):
            raise ValueError("Group timing must cover every declared frame")

    @classmethod
    def resolve(cls, recording_path: Path) -> "RecordingVideoSources":
        recording_path = recording_path.resolve(strict=True)
        group = VideoGroupHelper.from_recording_path(recording_path=str(recording_path))
        try:
            videos = group.video_metadata_by_id
            frame_numbers = tuple(range(group.frame_count))
            timing = RecordingGroupTiming.resolve(
                recording_folder=recording_path, videos=videos, frame_numbers=frame_numbers,
            )
            return cls(recording_path, camera_group_name(videos), tuple(
                CameraVideoSource(camera, video, timing.cameras[camera])
                for camera, video in videos.items()
            ), timing.synchronized)
        finally:
            group.close()


@dataclass(frozen=True)
class LoadedVideoFrame:
    frame_key: CameraFrameKey
    timestamp_s: float
    image_bgr: NDArray[np.uint8]
    read_seconds: float


@dataclass(frozen=True)
class VideoSourceFinished:
    execution_id: str
    sensor_group: str
    camera_id: str
    outcome: ProducerOutcome
    loaded_frames: int
    error_message: str | None


class ConcurrentVideoSources:
    """One sequential managed thread per video; bounded per-camera backend queues.

    Use as a context manager and consume events once. Closing cancels further reads
    and joins workers. A camera failure reports its own outcome, not global stop.
    Queue backpressure is source admission control, never a viewer acknowledgement.
    The consumer must bound its retained frames too; this adapter cannot enforce it.
    The supplied registry must be dedicated to these readers for their lifetime:
    its public reaping API removes all dead entries, not just selected workers.
    """
    def __init__(self, *, sources: RecordingVideoSources, execution_id: str,
                 registry: WorkerRegistry, shutdown_flag: Synchronized, queued_frames_per_camera: int = 2) -> None:
        if not execution_id.strip() or type(queued_frames_per_camera) is not int or queued_frames_per_camera < 1:
            raise ValueError("Execution identity and positive queue capacity are required")
        self.sources = sources
        self.execution_id = execution_id
        self.registry = registry
        self.shutdown_flag = shutdown_flag
        self._camera_events: dict[str, Queue[LoadedVideoFrame | VideoSourceFinished]] = {
            source.camera_id: Queue(maxsize=queued_frames_per_camera) for source in sources.camera_sources
        }
        self._stop = Event()
        self._workers = []
        self._camera_workers = {}
        self._finished_cameras: set[str] = set()
        self._started = False
        self._consumed = False
        self._consumer_mode: str | None = None

    def __enter__(self) -> "ConcurrentVideoSources":
        if self._started:
            raise RuntimeError("Video sources may only be started once")
        if self.registry.workers:
            raise ValueError("Video sources require a dedicated empty worker registry")
        self._started = True
        try:
            for source in self.sources.camera_sources:
                worker = self.registry.create_worker(
                    shutdown_flag=self.shutdown_flag,
                    worker_mode=WorkerMode.THREAD, target=self._read_camera,
                    name=f"VideoSource-{self.execution_id}-{source.camera_id}",
                    kwargs={"source": source},
                )
                worker.start()
                self._workers.append(worker)
                self._camera_workers[source.camera_id] = worker
            return self
        except BaseException:
            self.close()
            raise

    def _deliver(self, event: LoadedVideoFrame | VideoSourceFinished) -> None:
        camera = event.frame_key.camera if isinstance(event, LoadedVideoFrame) else event.camera_id
        while not self._stop.is_set() and not self.shutdown_flag.value:
            try:
                self._camera_events[camera].put(event, timeout=0.05)
                return
            except Full:
                continue

    def _read_camera(self, *, source: CameraVideoSource) -> None:
        loaded_frames = 0
        outcome = ProducerOutcome.SUCCEEDED
        error_message = None
        reader = None
        try:
            reader = SequentialVideoReader(path=source.video_metadata.file_path)
            for frame_number in range(source.video_metadata.frame_count):
                if self._stop.is_set() or self.shutdown_flag.value:
                    return
                start = perf_counter()
                pixels = reader.read_bgr(frame_number=frame_number)
                expected = (source.video_metadata.height, source.video_metadata.width, 3)
                if pixels.shape != expected or pixels.dtype != np.uint8:
                    raise ValueError(f"Unexpected image shape/type: {pixels.shape}/{pixels.dtype}; expected {expected}/uint8")
                read_seconds = perf_counter() - start
                pixels.setflags(write=False)
                self._deliver(LoadedVideoFrame(
                    CameraFrameKey(self.execution_id, self.sources.sensor_group, source.camera_id, frame_number),
                    source.camera_timing.timestamps_s[frame_number], pixels, read_seconds,
                ))
                loaded_frames += 1
        except Exception as error:
            outcome = ProducerOutcome.FAILED
            error_message = f"{type(error).__name__}: {error}"
        finally:
            if reader is not None:
                try:
                    reader.close()
                except Exception as error:
                    outcome = ProducerOutcome.FAILED
                    cleanup_error = f"Reader cleanup failed: {type(error).__name__}: {error}"
                    error_message = f"{error_message}; {cleanup_error}" if error_message else cleanup_error
        self._deliver(VideoSourceFinished(
            self.execution_id, self.sources.sensor_group, source.camera_id,
            outcome, loaded_frames, error_message,
        ))

    def read_camera_event(self, camera_id: str) -> LoadedVideoFrame | VideoSourceFinished:
        """Pull one camera without draining faster cameras into an unbounded buffer.

        Single backend consumer only; cannot mix with events(). Each camera has an
        independent queue so waiting on this camera never traps its data behind
        another camera's frames. Calls preserve each camera's source order.
        """
        if not self._started or self._consumer_mode == "events":
            raise RuntimeError("Start sources and choose only one consumption mode")
        self._consumer_mode = "camera"
        if camera_id in self._finished_cameras:
            raise RuntimeError("Camera terminal outcome was already consumed")
        queue = self._camera_events[camera_id]
        while True:
            if self._stop.is_set() or self.shutdown_flag.value:
                raise RuntimeError("Video source execution was cancelled")
            try:
                event = queue.get(timeout=0.05)
                if isinstance(event, VideoSourceFinished):
                    self._finished_cameras.add(camera_id)
                return event
            except Empty:
                if not self._camera_workers[camera_id].is_alive() and queue.empty():
                    raise RuntimeError("No further event available for camera")

    def events(self) -> Iterator[LoadedVideoFrame | VideoSourceFinished]:
        if not self._started or self._consumed or self._consumer_mode is not None:
            raise RuntimeError("Start sources and consume their events exactly once")
        self._consumed = True
        self._consumer_mode = "events"
        remaining = deque(self._camera_events)
        while remaining:
            if self._stop.is_set() or self.shutdown_flag.value:
                raise RuntimeError("Video source execution was cancelled")
            camera = remaining.popleft()
            try:
                event = self._camera_events[camera].get(timeout=0.05)
            except Empty:
                remaining.append(camera)
                if all(not worker.is_alive() for worker in self._workers) and all(
                    self._camera_events[item].empty() for item in remaining
                ):
                    raise RuntimeError("Video workers exited without all terminal outcomes")
                continue
            if not isinstance(event, VideoSourceFinished):
                remaining.append(camera)
            yield event

    def close(self) -> None:
        self._stop.set()
        for worker in self._workers:
            worker.mark_stopping()
            worker.join(timeout=10.0)
        alive = [worker for worker in self._workers if worker.is_alive()]
        # Public registry reaping also handles workers registered by create_worker
        # whose start failed. Running workers remain registered for supervision.
        self.registry.remove_dead()
        if not alive:
            self._workers.clear()
            self._camera_workers.clear()
        for queue in self._camera_events.values():
            while True:
                try:
                    queue.get_nowait()
                except Empty:
                    break
        if alive:
            raise RuntimeError(f"{len(alive)} video readers did not stop; native reads may still be running")

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
