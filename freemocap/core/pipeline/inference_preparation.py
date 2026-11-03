"""Application-managed worker for Tracker preparation and native retirement."""

import logging
import multiprocessing
from queue import Empty, Queue
from threading import Lock

from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellytracker.core.sessions.onnx_preparation import PreparationPhase

logger = logging.getLogger(__name__)


class InferencePreparation:
    def __init__(self, worker_registry):
        self._queue = Queue()
        self._jobs = set()
        self._retired = {}
        self._lock = Lock()
        self._closed = False
        self._shutdown = multiprocessing.Value("b", False)
        self.worker = worker_registry.create_worker(
            shutdown_flag=self._shutdown, worker_mode=WorkerMode.THREAD,
            target=self._run, name="InferencePreparation", log_queue=None,
        )

    def start(self):
        self.worker.start()

    def submit(self, job):
        with self._lock:
            if self._closed:
                raise RuntimeError("Preparation worker is closed")
            if job not in self._jobs and job.snapshot().phase == PreparationPhase.QUEUED:
                self._jobs.add(job)
                self._queue.put(job.run)

    def retire(self, resource):
        with self._lock:
            if self._closed:
                raise RuntimeError("Preparation worker is closed")
            self._retired[id(resource)] = resource
            self._queue.put(False)

    def _run(self):
        while True:
            try:
                callback = self._queue.get(timeout=0.05)
            except Empty:
                callback = False
            if callback is None:
                callback = False
            try:
                if callback:
                    callback()
            except Exception:
                logger.exception("Background inference preparation/cleanup failed")
            with self._lock:
                jobs = tuple(self._jobs)
            for job in jobs:
                runtime = getattr(job, "runtime", None)
                if self._closed and runtime is not None and runtime.status().alive:
                    try:
                        runtime.close()
                    except Exception:
                        logger.exception("Isolated runtime is still stopping")
                if job.snapshot().phase == PreparationPhase.STOPPING:
                    try:
                        job.dispose()
                    except Exception:
                        logger.exception("Background preparation disposal failed")
                if job.snapshot().phase in (
                    PreparationPhase.TRANSFERRED, PreparationPhase.FAILED, PreparationPhase.CANCELLED,
                ) and (runtime is None or not runtime.status().alive):
                    with self._lock:
                        self._jobs.discard(job)
            with self._lock:
                retired = tuple(self._retired.values())
            for resource in retired:
                try:
                    resource.close()
                except Exception:
                    logger.exception("Retired native resource is still stopping")
                else:
                    with self._lock:
                        self._retired.pop(id(resource), None)
            with self._lock:
                if self._closed and not self._jobs and not self._retired and self._queue.empty():
                    return

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                for job in self._jobs:
                    job.request_stop()
                    runtime = getattr(job, "runtime", None)
                    if runtime is not None:
                        runtime.request_stop()
                    self._queue.put(job.dispose)
                self._queue.put(None)
        self.worker.mark_stopping()
        self.worker.join(timeout=10.0)
        if self.worker.is_alive():
            raise RuntimeError("Native preparation is still running; shutdown did not finish")
