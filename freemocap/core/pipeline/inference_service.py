"""Application-owned inference scheduling with isolated pipeline tracking state."""

import multiprocessing
from contextlib import nullcontext
from time import perf_counter
from freemocap.core.pipeline.performance_report import PerformanceReport
from collections import deque
from concurrent.futures import CancelledError, Future
from dataclasses import dataclass, field, replace
from enum import StrEnum
from multiprocessing.sharedctypes import Synchronized
from threading import Condition
from uuid import uuid4

from freemocap.core.tasks.background_task_state import BackgroundTaskState
from freemocap.core.pipeline.posthoc.task_snapshot import TaskProgress

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
    performance: PerformanceReport | None = None
    timestamp_ms: int | None = None


@dataclass(slots=True)
class PendingInference:
    request: InferenceRequest
    submitted_at: float = field(default_factory=perf_counter)
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
    provider_status: tuple = ()
    _cuda_first: bool = False
    _preparation_job: object | None = None
    _preparation_finished: bool = False
    preparation_status: str | None = None
    _startup_ready: bool = False
    _preparation_supported: bool = False
    _preparation_intent: str | None = None
    _preparation_state: str | None = None
    _preparation_error: str | None = None
    _requested_provider: str | None = None
    _active_provider: str | None = None
    _trt_available: bool = False
    _preparation_task_id: str | None = None

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
        from freemocap.core.pipeline.inference_preparation import InferencePreparation
        self._preparation = InferencePreparation(worker_registry)
        self._condition = Condition()
        self._clients: deque[InferenceClient] = deque()
        self._shutdown = multiprocessing.Value("b", False)
        self._closed = False
        self._realtime_streak = 0
        self._startup_records: dict[str, dict] = {}
        self._retirements: dict[int, object] = {}
        self.preparation_task_state = BackgroundTaskState()
        self._preparation_task_clients: dict[str, InferenceClient] = {}
        self.worker = worker_registry.create_worker(
            shutdown_flag=self._shutdown, worker_mode=WorkerMode.THREAD,
            target=self._run, name="SharedInference", log_queue=None,
        )

    def start(self) -> None:
        self._preparation.start()
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
            self._record_startup(client, "waiting_for_frames", "Waiting for the first camera frame")
            return client

    def _record_startup(self, client: InferenceClient, phase: str, message: str, error: str | None = None) -> None:
        with self._condition:
            now = perf_counter()
            previous = self._startup_records.get(client.registration.pipeline_id)
            self._startup_records[client.registration.pipeline_id] = {
                "phase": phase, "message": message, "error": error,
                "started": previous["started"] if previous else now,
                "phase_started": now,
                "finished": now if phase in ("running", "failed") else None,
            }
            while len(self._startup_records) > 32:
                self._startup_records.pop(next(iter(self._startup_records)))

    def startup_status(self, pipeline_id: str) -> dict | None:
        """Read startup progress without querying a native model or waiting on it."""
        with self._condition:
            record = self._startup_records.get(pipeline_id)
            if record is None:
                return None
            now = record["finished"] or perf_counter()
            return {"status": "failed" if record["error"] else ("ready" if record["phase"] == "running" else "running"),
                    "phase": record["phase"], "message": record["message"], "error": record["error"],
                    "elapsed_seconds": now - record["started"],
                    "phase_elapsed_seconds": now - record["phase_started"]}

    def has_result(self, pipeline_id: str) -> bool:
        """Lightweight frame-delivery gate; no snapshot allocation or native call."""
        with self._condition:
            record = self._startup_records.get(pipeline_id)
            return record is not None and record["phase"] == "running"

    def _preparation_client(self, pipeline_id: str) -> InferenceClient:
        client = next((item for item in self._clients if item.registration.pipeline_id == pipeline_id
                       and not item._closed and not item.registration.shutdown_flag.value), None)
        if client is None:
            raise ValueError("No running pipeline with this identifier")
        return client

    def preparation_status(self, pipeline_id: str) -> dict:
        """Read only cached diagnostics and isolated-worker lifecycle metadata."""
        with self._condition:
            client = self._preparation_client(pipeline_id)
            return self._preparation_status_locked(client)

    def _preparation_status_locked(self, client: InferenceClient) -> dict:
        from skellytracker.core.sessions.onnx_preparation import PreparationPhase
        job = client._preparation_job
        state = "idle" if client._preparation_supported and client._startup_ready else "unavailable"
        phase, elapsed, model = state, 0.0, None
        error = client._preparation_error
        pending_cleanup = False
        native_alive = False
        if job is not None:
            snapshot = job.snapshot()
            phase, elapsed = snapshot.phase.value, snapshot.elapsed_seconds
            state = {
                PreparationPhase.QUEUED: "queued", PreparationPhase.BUILDING: "running",
                PreparationPhase.VALIDATING: "running", PreparationPhase.READY: "ready",
                PreparationPhase.STOPPING: "stopping", PreparationPhase.DISPOSING: "stopping",
                PreparationPhase.FAILED: "failed", PreparationPhase.CANCELLED: "cancelled",
                PreparationPhase.TRANSFERRED: "activated",
            }[snapshot.phase]
            error = error or snapshot.reason
            runtime = getattr(job, "runtime", None)
            if runtime is not None:
                native = runtime.status()
                native_alive = native.alive
                if state == "running":
                    phase, model = native.phase, native.model_name
                pending_cleanup = native.alive and state in ("failed", "cancelled", "stopping")
        state = (client._preparation_state or state) if not client._closed else state
        if client._preparation_state is not None and not client._closed:
            phase = client._preparation_state
        pending_cleanup = pending_cleanup or (native_alive and state in ("failed", "cancelled", "stopping"))
        if client._preparation_intent is not None and not client._closed:
            state = "queued" if client._preparation_intent == "prepare" else "stopping"
            phase = state
        if client._active_provider == "trt":
            state = phase = "activated"
        can_prepare = (not client._closed and client._preparation_supported and client._startup_ready
                       and client._active_provider == "cuda" and not pending_cleanup
                       and state in ("idle", "failed", "cancelled"))
        message = client.preparation_status
        if state == "failed" and client._preparation_state is None:
            message = "TensorRT preparation failed; CUDA remains active"
        elif state == "cancelled":
            message = "TensorRT preparation cancelled; CUDA remains active"
        return {
            "pipeline_id": client.registration.pipeline_id, "status": state, "phase": phase,
            "elapsed_seconds": elapsed, "model_name": model,
            "message": message, "error": error,
            "can_prepare": can_prepare,
            "can_cancel": not client._closed and state in ("queued", "running", "ready", "stopping"),
            "requested_provider": client._requested_provider, "active_provider": client._active_provider,
        }

    def request_preparation(self, pipeline_id: str) -> dict:
        with self._condition:
            client = self._preparation_client(pipeline_id)
            if not self.preparation_status(pipeline_id)["can_prepare"]:
                raise ValueError("TensorRT preparation is unavailable or its previous worker has not stopped")
            self._publish_preparation_tasks_locked()
            client._preparation_task_id = f"onnx_preparation:{uuid4().hex}"
            self.preparation_task_state.register(client._preparation_task_id, "onnx_preparation")
            self._preparation_task_clients[client._preparation_task_id] = client
            client._preparation_intent = "prepare"
            client._preparation_state = None
            client._preparation_error = None
            client.preparation_status = "Preparing TensorRT in an isolated worker; CUDA remains active"
            self._publish_preparation_tasks_locked()
            self._condition.notify_all()
            return self.preparation_status(pipeline_id)

    def cancel_preparation(self, pipeline_id: str) -> dict:
        with self._condition:
            client = self._preparation_client(pipeline_id)
            if not self.preparation_status(pipeline_id)["can_cancel"]:
                raise ValueError("No pending TensorRT preparation to cancel")
            client._preparation_intent = "cancel"
            client.preparation_status = "Stopping the isolated preparation worker; CUDA remains active"
            self._publish_preparation_tasks_locked()
            self._condition.notify_all()
            return self.preparation_status(pipeline_id)

    def preparation_tasks_snapshot(self):
        """Refresh retained jobs for the existing task-progress delivery path."""
        with self._condition:
            self._publish_preparation_tasks_locked(refresh_elapsed=True)
            return self.preparation_task_state.snapshot()

    def cancel_preparation_task(self, task_id: str) -> bool:
        with self._condition:
            client = self._preparation_task_clients.get(task_id)
            if client is None or client._preparation_task_id != task_id or client._closed:
                return False
            self.cancel_preparation(client.registration.pipeline_id)
            return True

    def _publish_preparation_tasks_locked(self, *, refresh_elapsed: bool = False) -> None:
        for task_id, client in tuple(self._preparation_task_clients.items()):
            result = self._preparation_status_locked(client)
            if client._closed and client._preparation_job is None:
                result.update(status="cancelled", phase="cancelled", can_prepare=False, can_cancel=False)
            state = result["status"]
            # READY still awaits adoption; failure/cancel with live cleanup is not terminal yet.
            status = {"activated": "complete", "failed": "failed", "cancelled": "cancelled",
                      "queued": "queued"}.get(state, "running")
            job = client._preparation_job
            runtime = getattr(job, "runtime", None) if job is not None else None
            if status in ("failed", "cancelled") and runtime is not None and runtime.status().alive:
                status = "running"
            previous = self.preparation_task_state.tasks.get(task_id)
            if (not refresh_elapsed and previous is not None and previous.status == status
                    and previous.result is not None
                    and {key: value for key, value in previous.result.items() if key != 'elapsed_seconds'}
                    == {key: value for key, value in result.items() if key != 'elapsed_seconds'}):
                continue
            self.preparation_task_state.update(task_id, status=status, result=result, error=result["error"],
                cancellation_requested=state in ("stopping", "cancelled"),
                progress=TaskProgress(phase=result["phase"], progress_fraction=None,
                                      detail=result["message"] or result["phase"]))
            if status not in ("queued", "running"):
                del self._preparation_task_clients[task_id]

    def _initial_sessions(self, client: InferenceClient) -> tuple[SessionRequest, ...]:
        requests = []
        for request in client.registration.sessions:
            config = request.config
            if config.backend == "onnx":
                client._requested_provider = config.execution_provider
                client._active_provider = config.execution_provider
                if client.registration.mode == InferenceMode.REALTIME and config.execution_provider in (None, "trt"):
                    from freemocap.core.tracking.execution_providers import advertised_providers
                    available = advertised_providers()
                    client._trt_available = "trt" in available
                    safe = next((name for name in ("cuda", "coreml", "directml", "cpu") if name in available), None)
                    if safe is None:
                        raise ValueError("No non-TensorRT provider is available for realtime startup")
                    client._cuda_first = safe == "cuda"
                    client._active_provider = safe
                    if not client._cuda_first:
                        config = config.model_copy(deep=True)
                        config.execution_provider = safe
                        request = SessionRequest(session_type=request.session_type, config=config)
            requests.append(request)
        return tuple(requests)

    def _inspect_client_providers(self, client: InferenceClient) -> tuple:
        from freemocap.core.tracking.execution_providers import inspect_tracker_providers
        requests = []
        for request in client.registration.sessions:
            if request.config.backend == "onnx" and client._active_provider is not None:
                config = request.config.model_copy(deep=True)
                config.execution_provider = client._active_provider
                request = SessionRequest(session_type=request.session_type, config=config)
            requests.append(request)
        statuses = inspect_tracker_providers(client._lease.tracker, tuple(requests))
        return tuple(replace(item, requested_provider=client._requested_provider) for item in statuses)

    def _process_preparation_intents(self, pool: SharedSessionPool) -> None:
        with self._condition:
            intents = [(item, item._preparation_intent) for item in self._clients
                       if item._preparation_intent is not None and not item._closed]
            for client, intent in intents:
                client._preparation_intent = None
                client._preparation_state = "queued" if intent == "prepare" else "stopping"
        for client, intent in intents:
            try:
                if intent == "cancel":
                    if client._preparation_job is not None:
                        client._preparation_job.request_stop()
                        client._preparation_state = None
                    else:
                        client._preparation_state = "cancelled"
                        client.preparation_status = "Preparation cancelled; CUDA remains active"
                else:
                    job = pool.prepare_onnx(lease=client._lease, isolated=True, retry=True)
                    if job is None:
                        raise ValueError("The selected detector recipe cannot use TensorRT")
                    client._preparation_job = job
                    client._preparation_finished = False
                    client._preparation_state = None
                    self._preparation.submit(job)
            except Exception as error:
                with self._condition:
                    client._preparation_state = "failed"
                    client._preparation_error = str(error)
                    client.preparation_status = "TensorRT preparation failed; CUDA remains active"

    def _activate_ready_preparations(self, pool: SharedSessionPool) -> None:
        from skellytracker.core.sessions.onnx_preparation import PreparationPhase
        with self._condition:
            clients = [item for item in self._clients if item._preparation_job is not None
                       and not item._preparation_finished and not item._closed]
        for client in clients:
            job = client._preparation_job
            if job.snapshot().phase not in (PreparationPhase.READY, PreparationPhase.TRANSFERRED):
                continue
            try:
                activation = pool.activate_prepared(lease=client._lease, job=job)
                if activation.cleanup is not None:
                    with self._condition:
                        self._retirements[id(activation.cleanup)] = activation.cleanup
                with self._condition:
                    if activation.activated:
                        client._preparation_state = "activated"
                        client.preparation_status = "TensorRT is active"
                    else:
                        client._preparation_state = "failed"
                        client._preparation_error = activation.error
                        client.preparation_status = "TensorRT activation failed; CUDA remains active"
                    client._preparation_finished = True
            except Exception as error:
                try:
                    job.request_stop()
                except Exception as stop_error:
                    error = RuntimeError(f"{error}; native cleanup is pending: {stop_error}")
                with self._condition:
                    client._preparation_state = "failed"
                    client._preparation_error = str(error)
                    client.preparation_status = "TensorRT activation failed"
                    client._preparation_finished = True
            self._refresh_shared_providers(pool)
        self._drain_retirements()

    def _refresh_shared_providers(self, pool: SharedSessionPool) -> None:
        with self._condition:
            clients = [item for item in self._clients if item._lease is not None and not item._closed]
        for client in clients:
            try:
                actual = pool.onnx_provider(lease=client._lease)
                if actual is None or actual == client._active_provider:
                    continue
                with self._condition:
                    client._active_provider = actual
                    if actual == "trt":
                        client._preparation_state = "activated"
                        client._preparation_finished = True
                        client.preparation_status = "TensorRT is active"
                    client._preparation_supported = (client._cuda_first and client._trt_available
                                                     and pool.can_prepare_onnx(lease=client._lease))
                statuses = self._inspect_client_providers(client)
                with self._condition:
                    client.provider_status = statuses
            except Exception as error:
                with self._condition:
                    client._preparation_error = str(error)
                    client.preparation_status = f"Using {client._active_provider}; provider diagnostics failed"

    def _drain_retirements(self) -> None:
        """Keep resource ownership if queuing cleanup temporarily fails."""
        with self._condition:
            resources = tuple(self._retirements.items())
        for identifier, resource in resources:
            try:
                self._preparation.retire(resource)
            except Exception:
                continue
            with self._condition:
                self._retirements.pop(identifier, None)

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
                self._process_preparation_intents(pool)
                self._activate_ready_preparations(pool)
                with self._condition:
                    self._publish_preparation_tasks_locked()
                if client is None or pending is None:
                    with self._condition:
                        # Submission and retirement can occur while leases are released.
                        # Check the queue under the condition lock before sleeping.
                        if not self._shutdown.value and not any(
                            item._pending is not None or item._preparation_intent is not None or item._closed or item.registration.shutdown_flag.value
                            for item in self._clients
                        ):
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
                    performance = pending.request.performance
                    if performance is not None:
                        performance.record("inference.queue_wait", perf_counter() - pending.submitted_at)
                    if client._lease is None:
                        self._record_startup(client, "loading_models", "Loading tracking models")
                        with performance.measure("inference.session_setup") if performance is not None else nullcontext():
                            initial_sessions = self._initial_sessions(client)
                            client._lease = pool.create_tracker(
                                config=client.registration.tracker_config, requests=initial_sessions,
                                **({"cuda_first": True} if client._cuda_first else {}),
                                **({"progress": lambda phase, model: self._record_startup(client, phase, model)}
                                   if any(item.config.backend == "onnx" for item in client.registration.sessions) else {}),
                            )
                            if any(item.config.backend == "onnx" for item in initial_sessions):
                                client._active_provider = pool.onnx_provider(lease=client._lease)
                            statuses = self._inspect_client_providers(client)
                            client._preparation_supported = (client._cuda_first and client._trt_available
                                                             and pool.can_prepare_onnx(lease=client._lease))
                            with self._condition:
                                client.provider_status = statuses
                                if client._active_provider == "trt":
                                    client._preparation_state = "activated"
                                    client.preparation_status = "TensorRT is active"
                                elif client._cuda_first and client._preparation_supported:
                                    client.preparation_status = ("TensorRT preparation required; CUDA is running"
                                                                 if client._requested_provider == "trt" else
                                                                 "Using CUDA; automatic TensorRT preparation is disabled")
                                elif client._cuda_first:
                                    client.preparation_status = (
                                        "Using CUDA; TensorRT provider is unavailable" if not client._trt_available else
                                        "Using CUDA; this detector recipe does not support TensorRT")
                                elif client._requested_provider == "trt":
                                    client.preparation_status = ("TensorRT preparation requires available CUDA and TensorRT providers; "
                                                                 f"using {client._active_provider}")
                                elif client._active_provider is None:
                                    client.preparation_status = "This pipeline has no ONNX acceleration backend"
                                elif client._requested_provider is None:
                                    client.preparation_status = (f"Using {client._active_provider}; TensorRT preparation requires "
                                                                 "available CUDA and TensorRT providers")
                                else:
                                    client.preparation_status = f"Using explicitly selected {client._active_provider}"
                            self._record_startup(client, "waiting_for_first_result", "Processing the first camera frame")
                    with performance.measure(f"inference.process_batch.images={len(pending.request.images)}") if performance is not None else nullcontext():
                        observations, client._states = client._lease.tracker.process_batch(
                            images=pending.request.images, frame_number=pending.request.frame_number, states=client._states,
                            **({"timestamp_ms": pending.request.timestamp_ms} if pending.request.timestamp_ms is not None else {}),
                        )
                    if observations.keys() != pending.request.images.keys():
                        raise ValueError("Inference results do not match the requested sources")
                    if any(observation.frame_number != pending.request.frame_number for observation in observations.values()):
                        raise ValueError("Inference results do not match the requested frame number")
                except Exception as error:
                    self._record_startup(client, "failed", "Tracking startup or processing failed", str(error))
                    client.registration.shutdown_flag.value = True
                    with self._condition:
                        client._active = None
                        client._closed = True
                        client.failure = error
                        pending.result.set_exception(error)
                else:
                    if not client._startup_ready:
                        self._record_startup(client, "running", "Tracking is producing results")
                        client._startup_ready = True
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

    def provider_status(self) -> list[dict]:
        """Read immutable startup diagnostics without touching native sessions."""
        from dataclasses import asdict
        with self._condition:
            return [{"pipeline_id": client.registration.pipeline_id,
                     "mode": client.registration.mode.value,
                     "models": [asdict(status) for status in client.provider_status],
                     "preparation": client.preparation_status or (
                         asdict(client._preparation_job.snapshot()) if client._preparation_job is not None else None)}
                    for client in self._clients if not client._closed]

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._shutdown.value = True
            self._condition.notify_all()
        self.worker.mark_stopping()
        self.worker.join(timeout=10.0)
        if self.worker.is_alive():
            raise RuntimeError("Inference is still executing native code; service shutdown did not finish")
        self._drain_retirements()
        if self._retirements:
            raise RuntimeError("Native cleanup could not be queued; service still owns retired resources")
        self._preparation.close()
        self.preparation_tasks_snapshot()
