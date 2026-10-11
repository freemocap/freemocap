"""Stream bounded camera batches through the application's existing inference service.

No model/session construction or detector algorithms are implemented here.
This is a backend iterator, not a WebSocket or UI-driven execution loop.
"""
from collections.abc import Iterator
from concurrent.futures import CancelledError, TimeoutError
from dataclasses import dataclass
import multiprocessing
import math
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellytracker.core import TrackerConfig
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.sessions.execution_provider_name import ExecutionProviderName

from freemocap.core.pipeline.dataflow.camera_join import CameraFrameKey, ProducerOutcome
from freemocap.core.pipeline.dataflow.video_sources import (
    ConcurrentVideoSources, LoadedVideoFrame, RecordingVideoSources, VideoSourceFinished,
)
from freemocap.core.pipeline.inference_service import (
    InferenceMode, InferenceRegistration, InferenceRequest, InferenceService,
)
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.tracking.tracker_factory import tracker_session_requests


@dataclass(frozen=True)
class TrackedCameraFrame:
    frame_key: CameraFrameKey
    timestamp_s: float
    observation: Observation


def recording_timestamps_ms(sources: RecordingVideoSources) -> tuple[int, ...]:
    """Relative recording time for temporal detectors, never processing wall time.

    Reject millisecond collisions instead of inventing an artificial time step.
    Original per-camera timestamps remain on the output data.
    """
    times = sources.group_timing.timestamps_s
    if not times or not all(math.isfinite(value) for value in times):
        raise ValueError("Tracking requires finite recording timestamps")
    result = tuple(round((value - times[0]) * 1000) for value in times)
    if any(right <= left for left, right in zip(result, result[1:])):
        raise ValueError("Tracking timestamps must be strictly increasing at millisecond resolution")
    return result


class SkellyTrackerAdapter:
    def __init__(self, *, inference_service: InferenceService,
                 tracker_config: TrackerConfig, performance_report: PerformanceReport,
                 execution_provider: ExecutionProviderName | None = None,
                 mediapipe_disable_gpu: bool | None = None) -> None:
        self.inference_service = inference_service
        self.tracker_config = tracker_config.model_copy(deep=True)
        self.performance_report = performance_report
        self.execution_provider = execution_provider
        self.mediapipe_disable_gpu = mediapipe_disable_gpu

    def track_recording(self, *, sources: RecordingVideoSources, execution_id: str,
                        shutdown_flag: Synchronized, queued_frames_per_camera: int = 2,
                        ) -> Iterator[TrackedCameraFrame | VideoSourceFinished]:
        """One in-flight inference batch plus bounded read-ahead per camera.

        Close the iterator on early exit. Successful source outcomes arrive after
        that camera's observations have been yielded; they are not scientific sink
        acceptance. Source failures allow remaining cameras to continue. An opaque
        inference-batch failure raises without attributing it to an individual camera
        or changing the caller's graph cancellation flag. No automatic stateful retry.
        """
        client_shutdown = multiprocessing.Value("b", False)
        timestamps_ms = recording_timestamps_ms(sources)
        camera_count = len(sources.camera_sources)
        client = self.inference_service.register(InferenceRegistration(
            pipeline_id=execution_id, mode=InferenceMode.POSTHOC,
            tracker_config=self.tracker_config,
            sessions=tracker_session_requests(config=self.tracker_config, batch_size=camera_count,
                                              execution_provider=self.execution_provider,
                                              mediapipe_disable_gpu=self.mediapipe_disable_gpu),
            shutdown_flag=client_shutdown,
        ))
        active_cameras = [source.camera_id for source in sources.camera_sources]
        frame_count = sources.camera_sources[0].video_metadata.frame_count
        try:
            # Registry public cleanup is all-dead, not owner-scoped. Keep reader
            # lifecycle separate from the application-owned inference service.
            source_registry = WorkerRegistry(global_kill_flag=shutdown_flag, worker_mode=WorkerMode.THREAD)
            with ConcurrentVideoSources(
                sources=sources, execution_id=execution_id, registry=source_registry,
                shutdown_flag=shutdown_flag, queued_frames_per_camera=queued_frames_per_camera,
            ) as readers:
                for frame_number in range(frame_count + 1):
                    batch_frames: dict[str, LoadedVideoFrame] = {}
                    source_outcomes: list[VideoSourceFinished] = []
                    with self.performance_report.measure("graph.camera_batch_wait"):
                        for camera in tuple(active_cameras):
                            event = readers.read_camera_event(camera)
                            if isinstance(event, VideoSourceFinished):
                                if event.outcome == ProducerOutcome.SUCCEEDED and event.loaded_frames != frame_count:
                                    raise ValueError("Successful video source has incomplete coverage")
                                active_cameras.remove(camera)
                                source_outcomes.append(event)
                                continue
                            expected = CameraFrameKey(execution_id, sources.sensor_group, camera, frame_number)
                            if event.frame_key != expected:
                                raise ValueError("Video result does not match the expected camera/frame identity")
                            batch_frames[camera] = event
                    yield from source_outcomes
                    if not batch_frames:
                        break
                    if shutdown_flag.value:
                        raise CancelledError("Graph execution cancelled before inference")
                    future = client.submit(InferenceRequest(
                        frame_number=frame_number,
                        images={camera: frame.image_bgr for camera, frame in batch_frames.items()},
                        performance=self.performance_report,
                        timestamp_ms=timestamps_ms[frame_number],
                    ))
                    while True:
                        try:
                            observations = future.result(timeout=0.05)
                            break
                        except TimeoutError:
                            if future.done():
                                raise
                            if shutdown_flag.value:
                                client.close()
                                raise CancelledError("Graph execution cancelled during inference")
                    if shutdown_flag.value:
                        raise CancelledError("Graph execution cancelled after inference")
                    # Drop adapter image references before yielding observations.
                    frame_metadata = {camera: (frame.frame_key, frame.timestamp_s)
                                      for camera, frame in batch_frames.items()}
                    batch_frames.clear()
                    del event
                    self.performance_report.frames += 1
                    self.performance_report.images += len(observations)
                    stage_counts: dict[str, int] = {}
                    for observation in observations.values():
                        for name, stage in observation.stages.items():
                            for metric, count in (("camera_images", 1), ("object_detector_runs", int(stage.detector_ran))):
                                label = f"tracking.{name}.{metric}"
                                stage_counts[label] = stage_counts.get(label, 0) + count
                    self.performance_report.increment_counts(stage_counts)
                    for camera, observation in observations.items():
                        key, timestamp = frame_metadata[camera]
                        yield TrackedCameraFrame(key, timestamp, observation)
        finally:
            client.close()
