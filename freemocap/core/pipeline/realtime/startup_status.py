"""Observable realtime startup state; elapsed time is measured, not an ETA."""

from threading import Event, Lock
from time import monotonic


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

    def begin(self) -> None:
        with self._lock:
            self.stop_requested.clear()
            self._started = self._phase_started = monotonic()
            self._ended = None
            self._status = "running"
            self._phase = "starting"
            self._pipeline_id = self._message = self._error = None
            self._inference_ready_observed = False
            self._preview_ready = False

    def record_preview_delivery(self) -> None:
        """Observe a successfully sent image without implying processing readiness."""
        with self._lock:
            self._preview_ready = True

    def phase(self, name: str) -> None:
        with self._lock:
            if self._status in ("running", "stopping"):
                if name != self._phase:
                    self._phase_started = monotonic()
                self._phase = name

    def pipeline_created(self, pipeline_id: str) -> None:
        with self._lock:
            self._pipeline_id = pipeline_id
            self._phase = "waiting_for_frames"
            self._phase_started = monotonic()

    def ready(self) -> None:
        with self._lock:
            if self._status != "running":
                return
            self._status = self._phase = "ready"
            self._ended = self._phase_started = monotonic()

    def record_frame_delivery(self, pipeline_id: str) -> None:
        """Mark ready only after delivery from this startup's pipeline."""
        with self._lock:
            if self._status == "running" and self._pipeline_id == pipeline_id:
                self._status = self._phase = "ready"
                self._message = "Live frames are streaming"
                self._ended = self._phase_started = monotonic()

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

    def fail(self, error: str) -> None:
        with self._lock:
            self._status = "failed"
            self._error = error
            self._ended = monotonic()

    def stopped(self, message: str = "Startup request stopped; camera capture remains independently managed") -> None:
        with self._lock:
            self._status = self._phase = "stopped"
            self._message = message
            self._ended = self._phase_started = monotonic()

    def request_stop(self) -> bool:
        with self._lock:
            if self._status not in ("running", "stopping"):
                return False
            self.stop_requested.set()
            self._status = "stopping"
            self._message = "Waiting for the current operation to finish before stopping"
            return True

    def snapshot(self) -> dict:
        with self._lock:
            now = self._ended if self._ended is not None else monotonic()
            return {
                "status": self._status,
                "phase": self._phase,
                "elapsed_seconds": 0.0 if self._started is None else now - self._started,
                "phase_elapsed_seconds": 0.0 if self._phase_started is None else now - self._phase_started,
                "pipeline_id": self._pipeline_id,
                "message": self._message,
                "error": self._error,
                "preview_ready": self._preview_ready,
            }
