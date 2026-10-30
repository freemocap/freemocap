"""Recording-owned annotation workers; pixels stay inside their video reader."""
from collections.abc import Callable
from concurrent.futures import CancelledError
from dataclasses import dataclass
import multiprocessing
from pathlib import Path
from queue import Queue, Empty
from threading import Lock
from time import perf_counter
from uuid import uuid4

import cv2
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core import TrackerConfig
from skellytracker.core.data_primitives.observation import Observation
from freemocap.core.tracking.observation_series import ObservationSeries, RecordingObservationSeries

from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.pipeline.posthoc.annotation_input import AnnotationInput
from freemocap.core.pipeline.posthoc.annotation_output import AnnotationOutputRequest, AnnotationVideoOutput
from freemocap.core.pipeline.posthoc.annotation_style import build_observation_annotator
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata


@dataclass(frozen=True)
class CameraAnnotationJob:
    recording_path: Path
    execution_id: str
    camera_id: str
    video: VideoMetadata
    tracker_config: TrackerConfig
    observations: tuple[Observation, ...] | ObservationSeries | RecordingObservationSeries
    run_id: int = 0


def write_camera_annotation(job: CameraAnnotationJob, *, cancelled: Callable[[], bool],
                            performance: PerformanceReport | None = None) -> Path:
    """The same complete-video operation for thread and process comparisons."""
    if cancelled():
        raise CancelledError("Annotation cancelled")
    annotator = build_observation_annotator(job.tracker_config)
    reader = cv2.VideoCapture(str(job.video.file_path))
    output = None
    try:
        if not reader.isOpened():
            raise ValueError(f"Cannot open annotation source: {job.video.file_path}")
        output = AnnotationVideoOutput(AnnotationOutputRequest(recording_path=job.recording_path,
            pipeline_id=job.execution_id, video=job.video, input_mode=AnnotationInput.RAW,
            performance=performance, camera_id=job.camera_id, run_id=job.run_id))
        for index in range(len(job.observations)):
            observation = (job.observations.annotation_frame(index) if isinstance(job.observations, (ObservationSeries, RecordingObservationSeries))
                           else job.observations[index])
            if cancelled():
                raise CancelledError("Annotation cancelled")
            if int(reader.get(cv2.CAP_PROP_POS_FRAMES)) != observation.frame_number:
                reader.set(cv2.CAP_PROP_POS_FRAMES, observation.frame_number)
            ok, image = reader.read()
            if not ok:
                raise ValueError("Annotation video ended before observations")
            output.write_frame(image=image, observation=observation, annotator=annotator)
        if cancelled():
            raise CancelledError("Annotation cancelled")
        output.publish()
        return output.destination
    finally:
        reader.release()
        if output is not None:
            output.close()


def _annotation_worker(*, connection, shutdown_flag) -> None:
    try:
        connection.send(("ready", None))
        while not shutdown_flag.value:
            if not connection.poll(0.1):
                continue
            job_id, job = connection.recv()
            performance = PerformanceReport()
            started = perf_counter()
            try:
                path = write_camera_annotation(job, cancelled=lambda: bool(shutdown_flag.value),
                                               performance=performance)
                result = dict(path=str(path), error=None)
            except Exception as error:
                result = dict(path=None, error=f"{type(error).__name__}: {error}",
                              cancelled=isinstance(error, CancelledError))
            result.update(seconds=perf_counter() - started, timings=performance.snapshot())
            connection.send((job_id, result))
            # Do not retain a completed camera's observations while idle.
            del job, result, performance
    except (EOFError, BrokenPipeError):
        pass
    finally:
        connection.close()


class RecordingAnnotationWorkers:
    """One recording's bounded worker set; close only this owner's workers.

    Blocking IPC stays on annotation handler threads, never on scientific handlers.
    Each worker has its own failure flag. No dropped-message progress channel is
    used for terminal results; one correlated job occupies one worker at a time.
    """
    def __init__(self, *, count: int = 2, registry: WorkerRegistry | None = None):
        if count < 1:
            raise ValueError("Annotation worker count must be positive")
        self.count = count
        self._owns_registry = registry is None
        self.registry = registry or WorkerRegistry(global_kill_flag=multiprocessing.Value("b", False),
                                                   worker_mode=WorkerMode.PROCESS)
        self.workers = []
        self._slots = []
        self._available = Queue()
        self._closed = False
        self.measurements = {}
        self.launch_seconds = 0.
        self.shutdown_seconds = 0.
        self._recording_identity = None
        self._identity_lock = Lock()

    def __enter__(self):
        if self.workers or self._closed:
            raise RuntimeError("Annotation workers cannot be restarted")
        started = perf_counter()
        try:
            for index in range(self.count):
                parent, child = multiprocessing.Pipe()
                flag = multiprocessing.Value("b", False)
                worker = self.registry.create_worker(shutdown_flag=flag, worker_mode=WorkerMode.PROCESS,
                    name=f"recording-annotation-{index}", target=_annotation_worker,
                    kwargs=dict(connection=child, shutdown_flag=flag))
                try:
                    worker.start()
                except BaseException:
                    parent.close()
                    raise
                finally:
                    child.close()
                self.workers.append(worker)
                self._slots.append([parent, flag, False])
                self._available.put(index)
        except BaseException:
            self.close()
            raise
        self.launch_seconds = perf_counter() - started
        return self

    def _receive(self, index: int, cancelled: Callable[[], bool]):
        connection, flag, _ = self._slots[index]
        while True:
            if cancelled() or self._closed:
                flag.value = True
                raise CancelledError("Annotation cancelled")
            if connection.poll(0.1):
                try:
                    return connection.recv()
                except EOFError as error:
                    raise RuntimeError("Annotation worker closed without a result") from error
            if not self.workers[index].is_alive():
                raise RuntimeError(f"Annotation worker exited with code {self.workers[index].exitcode}")

    def run_job(self, job: CameraAnnotationJob, *, cancelled: Callable[[], bool]) -> Path:
        if self._closed or not self.workers:
            raise RuntimeError("Annotation workers are not running")
        identity = (job.recording_path.resolve(), job.execution_id)
        with self._identity_lock:
            if self._recording_identity is None:
                self._recording_identity = identity
            elif self._recording_identity != identity:
                raise ValueError("Annotation workers belong to a different recording execution")
        while True:
            if cancelled() or self._closed:
                raise CancelledError("Annotation cancelled")
            try:
                index = self._available.get(timeout=0.1)
                break
            except Empty:
                if not any(worker.is_alive() for worker in self.workers):
                    raise RuntimeError("No annotation worker remains alive")
                continue
        try:
            connection, flag, ready = self._slots[index]
            started = perf_counter()
            if not ready:
                if self._receive(index, cancelled) != ("ready", None):
                    raise RuntimeError("Unexpected annotation startup reply")
                self._slots[index][2] = True
            ready_seconds = perf_counter() - started
            if flag.value or not self.workers[index].is_alive():
                raise RuntimeError("Annotation worker is unavailable")
            job_id = uuid4().hex
            connection.send((job_id, job))
            returned_id, result = self._receive(index, cancelled)
            if returned_id != job_id:
                raise RuntimeError("Annotation result belongs to another job")
            self.measurements[job.camera_id] = dict(result, ready_wait_seconds=ready_seconds,
                handler_seconds=perf_counter() - started)
            if result["error"]:
                if result.get("cancelled"):
                    raise CancelledError(result["error"])
                raise RuntimeError(result["error"])
            return Path(result["path"])
        finally:
            if self.workers[index].is_alive() and not self._slots[index][1].value:
                self._available.put(index)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        started = perf_counter()
        for worker, (_, flag, _) in zip(self.workers, self._slots):
            worker.mark_stopping()
            flag.value = True
        try:
            for worker in self.workers:
                worker.terminate_gracefully()
        finally:
            for connection, _, _ in self._slots:
                connection.close()
            if self._owns_registry:
                self.registry.remove_dead()
            self.shutdown_seconds = perf_counter() - started

    def __exit__(self, *args):
        self.close()
