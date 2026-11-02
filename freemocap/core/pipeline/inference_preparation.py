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
            self._queue.put(resource.close)

    def _run(self):
        while True:
            try:
                callback = self._queue.get(timeout=0.05)
            except Empty:
                callback = False
            if callback is None:
                return
            try:
                if callback:
                    callback()
            except Exception:
                logger.exception("Background inference preparation/cleanup failed")
            with self._lock:
                jobs = tuple(self._jobs)
            for job in jobs:
                if job.snapshot().phase == PreparationPhase.STOPPING:
                    try:
                        job.dispose()
                    except Exception:
                        logger.exception("Background preparation disposal failed")
                if job.snapshot().phase in (
                    PreparationPhase.TRANSFERRED, PreparationPhase.FAILED, PreparationPhase.CANCELLED,
                ):
                    with self._lock:
                        self._jobs.discard(job)

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                for job in self._jobs:
                    job.request_stop()
                    self._queue.put(job.dispose)
                self._queue.put(None)
        self.worker.mark_stopping()
        self.worker.join(timeout=10.0)
        if self.worker.is_alive():
            raise RuntimeError("Native preparation is still running; shutdown did not finish")
