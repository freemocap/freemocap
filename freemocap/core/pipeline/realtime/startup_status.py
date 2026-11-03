"""Observable realtime startup state; elapsed time is measured, not an ETA."""

from threading import Event, Lock
from time import monotonic
from uuid import uuid4

from freemocap.core.tasks.background_task_state import BackgroundTaskState
from freemocap.core.pipeline.posthoc.task_snapshot import TaskProgress


class RealtimeStartupStatus:
    def __init__(self) -> None:
        self.stop_requested = Event()
        self._lock = Lock()
        self._status = "idle"
        self._phase = "idle"
        self._started: float | None = None
        self._phase_started: float | None = None
        self._ended: float | None = None
        self._pipeline_id: str | None = None
        self._message: str | None = None
        self._error: str | None = None
        self._inference_ready_observed = False
        self._preview_ready = False
        self.task_state = BackgroundTaskState()
        self._task_id: str | None = None

    def begin(self) -> None:
        with self._lock:
            if self._task_id is not None and self._status in ("running", "stopping"):
                self._status = self._phase = "stopped"
                self._message = "Superseded by a newer startup request"
                self._ended = monotonic()
            self._publish_locked()
            self.stop_requested.clear()
            self._started = self._phase_started = monotonic()
            self._ended = None
            self._status = "running"
            self._phase = "starting"
            self._pipeline_id = self._message = self._error = None
            self._inference_ready_observed = False
            self._preview_ready = False
            self._task_id = f"realtime_startup:{uuid4().hex}"
            self.task_state.register(self._task_id, "realtime_startup")
            self._publish_locked()

    @property
    def task_id(self) -> str | None:
        with self._lock:
            return self._task_id

    def record_preview_delivery(self) -> None:
        """Observe a successfully sent image without implying processing readiness."""
        with self._lock:
            if not self._preview_ready:
                self._preview_ready = True
                self._publish_locked()

    def phase(self, name: str) -> None:
        with self._lock:
            if self._status in ("running", "stopping"):
                if name != self._phase:
                    self._phase_started = monotonic()
                self._phase = name
                self._publish_locked()

    def pipeline_created(self, pipeline_id: str) -> None:
        with self._lock:
            self._pipeline_id = pipeline_id
            self._phase = "waiting_for_frames"
            self._phase_started = monotonic()
            self._publish_locked()

    def ready(self) -> None:
        with self._lock:
            if self._status != "running":
                return
            self._status = self._phase = "ready"
            self._ended = self._phase_started = monotonic()
            self._publish_locked()

    def record_frame_delivery(self, pipeline_id: str) -> None:
        """Mark ready only after delivery from this startup's pipeline."""
        with self._lock:
            if self._status == "running" and self._pipeline_id == pipeline_id:
                self._status = self._phase = "ready"
                self._message = "Live frames are streaming"
                self._ended = self._phase_started = monotonic()
                self._publish_locked()

    def observe_inference(self, pipeline_id: str, *, status: str, phase: str,
                          phase_elapsed_seconds: float, message: str | None, error: str | None) -> None:
        """Merge inference progress only into the matching active startup.

        Waiting-for-stream timing starts once readiness is observed, rather than
        including earlier model loading or resetting on every HTTP poll.
        """
        with self._lock:
            if self._status != "running" or self._pipeline_id != pipeline_id:
                return
            now = monotonic()
            if status == "ready":
                if not self._inference_ready_observed:
                    self._phase_started = now
                    self._inference_ready_observed = True
                self._phase = "waiting_for_frames"
                self._message = "Tracking is ready; waiting for the first live frame to reach the stream"
            else:
                self._phase = phase
                self._phase_started = now - max(0.0, phase_elapsed_seconds)
                self._message = message
                if status == "failed":
                    self._status = "failed"
                    self._error = error or "Inference startup failed"
                    self._ended = now
            self._publish_locked()

    def fail(self, error: str) -> None:
        with self._lock:
            self._status = "failed"
            self._error = error
            self._ended = monotonic()
            self._publish_locked()

    def stopped(self, message: str = "Startup request stopped; camera capture remains independently managed") -> None:
        with self._lock:
            self._status = self._phase = "stopped"
            self._message = message
            self._ended = self._phase_started = monotonic()
            self._publish_locked()

    def request_stop(self) -> bool:
        with self._lock:
            if self._status not in ("running", "stopping"):
                return False
            self.stop_requested.set()
            self._status = "stopping"
            self._message = "Waiting for the current operation to finish before stopping"
            self._publish_locked()
            return True

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot_locked()

    def tasks_snapshot(self):
        with self._lock:
            self._publish_locked()
            return self.task_state.snapshot()

    def _snapshot_locked(self) -> dict:
        now = self._ended if self._ended is not None else monotonic()
        result = {
                "status": self._status,
                "phase": self._phase,
                "elapsed_seconds": 0.0 if self._started is None else now - self._started,
                "phase_elapsed_seconds": 0.0 if self._phase_started is None else now - self._phase_started,
                "pipeline_id": self._pipeline_id,
                "message": self._message,
                "error": self._error,
                "preview_ready": self._preview_ready,
            }
        result["delayed"] = result["status"] in ("running", "stopping") and result["phase_elapsed_seconds"] >= 15
        return result

    def _publish_locked(self) -> dict:
        result = self._snapshot_locked()
        if self._task_id is not None:
            status = {"ready": "complete", "stopped": "cancelled", "failed": "failed"}.get(self._status, "running")
            self.task_state.update(self._task_id, status=status, result=result, error=self._error,
                cancellation_requested=self.stop_requested.is_set(),
                progress=TaskProgress(phase=self._phase, progress_fraction=None, detail=self._message or self._phase))
        return result


def realtime_startup_snapshot(app) -> dict:
    """Project inference progress for both retained task delivery and explicit reads."""
    snapshot = app.startup_status.snapshot()
    if snapshot["pipeline_id"] and snapshot["status"] == "running":
        inference = app.inference_service.startup_status(snapshot["pipeline_id"])
        if inference is not None:
            app.startup_status.observe_inference(
                snapshot["pipeline_id"], **{key: inference[key] for key in (
                    "status", "phase", "phase_elapsed_seconds", "message", "error",
                )},
            )
            snapshot = app.startup_status.snapshot()
    return snapshot
