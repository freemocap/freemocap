"""Application-owned inference scheduling with isolated pipeline tracking state."""

import multiprocessing
from collections import deque
from concurrent.futures import CancelledError, Future
from dataclasses import dataclass, field
from enum import StrEnum
from multiprocessing.sharedctypes import Synchronized
from threading import Condition

import numpy as np
from numpy.typing import NDArray
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core import TrackerConfig
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.sessions.shared_sessions import SessionRequest, SharedSessionPool, TrackerLease
from skellytracker.core.tracker.tracker_state import TrackerState


class InferenceMode(StrEnum):
    REALTIME = "realtime"
    POSTHOC = "posthoc"


@dataclass(frozen=True, slots=True)
class InferenceRegistration:
    pipeline_id: str
    mode: InferenceMode
    tracker_config: TrackerConfig
    sessions: tuple[SessionRequest, ...]
    shutdown_flag: Synchronized


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """Images must remain unchanged until the returned future is terminal."""

    frame_number: int
    images: dict[str, NDArray[np.uint8]]


@dataclass(slots=True)
class PendingInference:
    request: InferenceRequest
    result: Future[dict[str, Observation]] = field(default_factory=Future)


@dataclass(eq=False)
class InferenceClient:
    registration: InferenceRegistration
    _service: "InferenceService"
    _pending: PendingInference | None = None
    _active: PendingInference | None = None
    _lease: TrackerLease | None = None
    _states: dict[str, TrackerState] = field(default_factory=dict)
    _last_frame: int = -1
    _closed: bool = False
    failure: Exception | None = None

    def submit(self, request: InferenceRequest) -> Future[dict[str, Observation]]:
        return self._service.submit(client=self, request=request)

    def close(self) -> None:
        self._service.release(client=self)


class InferenceService:
    """One managed execution thread; at most one outstanding request per client.

    Round-robin within each mode. After three realtime requests, ready posthoc
    work receives a turn. Requests are never combined across clients. Source
    adapters select the newest live frame before submitting; posthoc adapters
    submit every ordinal. Model and detector lifetime stays on this thread.
    """

    def __init__(self, *, worker_registry: WorkerRegistry) -> None:
        self._condition = Condition()
        self._clients: deque[InferenceClient] = deque()
        self._shutdown = multiprocessing.Value("b", False)
        self._closed = False
        self._realtime_streak = 0
        self.worker = worker_registry.create_worker(
            shutdown_flag=self._shutdown, worker_mode=WorkerMode.THREAD,
            target=self._run, name="SharedInference", log_queue=None,
        )

    def start(self) -> None:
        self.worker.start()

    def register(self, registration: InferenceRegistration) -> InferenceClient:
        with self._condition:
            if self._closed or self._shutdown.value or not self.worker.is_alive():
                raise RuntimeError("Inference service is not running")
            if any(client.registration.pipeline_id == registration.pipeline_id and not client._closed
                   for client in self._clients):
                raise ValueError(f"Inference already registered for pipeline {registration.pipeline_id}")
            snapshot = InferenceRegistration(
                pipeline_id=registration.pipeline_id, mode=registration.mode,
                tracker_config=registration.tracker_config.model_copy(deep=True),
                sessions=tuple(SessionRequest(session_type=item.session_type, config=item.config.model_copy(deep=True))
                               for item in registration.sessions),
                shutdown_flag=registration.shutdown_flag,
            )
            client = InferenceClient(registration=snapshot, _service=self)
            self._clients.append(client)
            return client

    def submit(self, *, client: InferenceClient, request: InferenceRequest) -> Future[dict[str, Observation]]:
        with self._condition:
            if client._service is not self or client._closed or self._closed or self._shutdown.value:
                raise RuntimeError("Inference client is closed")
            if client.registration.shutdown_flag.value:
                raise CancelledError("Pipeline stopped")
            if client._pending is not None or client._active is not None:
                raise RuntimeError("Wait for the outstanding inference request before submitting another")
            if not request.images or request.frame_number <= client._last_frame:
                raise ValueError("Inference requires nonempty images and increasing frame numbers")
            if client.registration.mode == InferenceMode.POSTHOC and request.frame_number != client._last_frame + 1:
                raise ValueError("Posthoc inference requires consecutive frame numbers starting at zero")
            pending = PendingInference(request=request)
            client._last_frame = request.frame_number
            client._pending = pending
            self._condition.notify_all()
            return pending.result

    def release(self, *, client: InferenceClient) -> None:
        with self._condition:
            if client._service is not self:
                raise ValueError("Inference client belongs to another service")
            client._closed = True
            if client._pending is not None:
                client._pending.result.cancel()
                client._pending = None
            self._condition.notify_all()

    def _select(self) -> InferenceClient | None:
        ready = [client for client in self._clients if client._pending is not None and not client._closed]
        posthoc = [client for client in ready if client.registration.mode == InferenceMode.POSTHOC]
        realtime = [client for client in ready if client.registration.mode == InferenceMode.REALTIME]
        candidates = posthoc if posthoc and (self._realtime_streak >= 3 or not realtime) else realtime
        if not candidates:
            return None
        client = candidates[0]
        self._clients.remove(client)
        self._clients.append(client)
        self._realtime_streak = self._realtime_streak + 1 if client.registration.mode == InferenceMode.REALTIME else 0
        return client

    def _run(self) -> None:
        pool = SharedSessionPool()
        try:
            while not self._shutdown.value:
                with self._condition:
                    retired = [client for client in self._clients
                               if client._closed or client.registration.shutdown_flag.value]
                    for client in retired:
                        self.release(client=client)
                        self._clients.remove(client)
                    client = self._select()
                    pending = client._pending if client is not None else None
                    if client is not None:
                        client._pending = None
                        client._active = pending
                for retired_client in retired:
                    if retired_client._lease is not None:
                        retired_client._lease.close()
                if client is None or pending is None:
                    with self._condition:
                        self._condition.wait(timeout=0.05)
                    continue
                if not pending.result.set_running_or_notify_cancel():
                    with self._condition:
                        client.registration.shutdown_flag.value = True
                        client._closed = True
                        client._active = None
                    continue
                try:
                    if client._closed or client.registration.shutdown_flag.value:
                        raise CancelledError("Pipeline stopped before inference")
                    if client._lease is None:
                        client._lease = pool.create_tracker(
                            config=client.registration.tracker_config, requests=client.registration.sessions,
                        )
                    observations, client._states = client._lease.tracker.process_batch(
                        images=pending.request.images, frame_number=pending.request.frame_number, states=client._states,
                    )
                    if observations.keys() != pending.request.images.keys():
                        raise ValueError("Inference results do not match the requested sources")
                    if any(observation.frame_number != pending.request.frame_number for observation in observations.values()):
                        raise ValueError("Inference results do not match the requested frame number")
                except Exception as error:
                    client.registration.shutdown_flag.value = True
                    with self._condition:
                        client._active = None
                        client._closed = True
                        client.failure = error
                        pending.result.set_exception(error)
                else:
                    with self._condition:
                        client._active = None
                        if client._closed or client.registration.shutdown_flag.value:
                            pending.result.set_exception(CancelledError("Pipeline stopped during inference"))
                        else:
                            pending.result.set_result(observations)
        finally:
            with self._condition:
                self._closed = True
                for client in self._clients:
                    client.registration.shutdown_flag.value = True
                    client._closed = True
                    client.failure = RuntimeError("Shared inference service stopped")
                    for pending in (client._pending, client._active):
                        if pending is not None and not pending.result.done():
                            pending.result.set_exception(client.failure)
                self._clients.clear()
                self._condition.notify_all()
            pool.close()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._shutdown.value = True
            self._condition.notify_all()
        self.worker.mark_stopping()
        self.worker.join(timeout=10.0)
        if self.worker.is_alive():
            raise RuntimeError("Inference is still executing native code; service shutdown did not finish")
