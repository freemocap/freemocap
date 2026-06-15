"""PupilLabsManager — lifecycle management for the Pupil Labs ZMQ bridge.

Owns a daemon thread that connects to Pupil Capture's IPC Backbone,
subscribes to 3D pupil and gaze topics, and accumulates :class:`PupilFramePayload`
samples into a thread-safe deque. The main thread drains the deque and
computes a per-field median to attach to each camera frame's
:class:`~freemocap.core.viz.frontend_payload.FrontendPayload`.
"""

import collections
import logging
import queue
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from freemocap.core.pupil.pupil_data_models import (
    Pupil3dEyeballData,
    PupilFramePayload,
    PupilGazeData,
)
from freemocap.core.pupil.pupil_labs_config import PupilLabsConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Median helpers
# ---------------------------------------------------------------------------

def _median_struct(items: list) -> object:
    """Compute element-wise median of a list of msgspec Struct instances.

    Each numeric field is reduced via :func:`statistics.median`. Fields
    where ALL values are ``None`` stay ``None``.

    Args:
        items: Non-empty list of same-type msgspec Struct instances.

    Returns:
        A new instance of the same type with median field values.
    """
    import msgspec

    if len(items) == 1:
        return items[0]

    cls = type(items[0])
    field_infos = msgspec.structs.fields(cls)
    kwargs: dict[str, float | None] = {}

    for fi in field_infos:
        values = []
        for item in items:
            v = getattr(item, fi.name)
            if v is not None:
                values.append(v)
        if values:
            kwargs[fi.name] = statistics.median(values)
        else:
            kwargs[fi.name] = None  # field not present in any sample

    return cls(**kwargs)


def _compute_median_payload(frames: list[PupilFramePayload]) -> PupilFramePayload:
    """Compute per-field median across multiple :class:`PupilFramePayload` frames.

    Pupil data arrives at ~120 Hz while camera frames emit at ~30 Hz,
    yielding ~4 pupil frames per camera frame. Taking the median smooths
    out per-sample noise.

    Args:
        frames: Non-empty list of pupil frames accumulated since the
                last camera frame.

    Returns:
        A single :class:`PupilFramePayload` with median values.
    """
    if len(frames) == 1:
        return frames[0]

    # Group per-eye data across frames
    eyeball_by_eye: dict[int, list[Pupil3dEyeballData]] = {}
    gaze_by_eye: dict[int, list[PupilGazeData]] = {}

    for frame in frames:
        for eb in frame.eyeballs:
            eyeball_by_eye.setdefault(eb.eye_id, []).append(eb)
        for gz in frame.gazes:
            gaze_by_eye.setdefault(gz.eye_id, []).append(gz)

    median_eyeballs = [_median_struct(ebs) for ebs in eyeball_by_eye.values()]
    median_gazes = [_median_struct(gzs) for gzs in gaze_by_eye.values()]

    return PupilFramePayload(
        timestamp=statistics.median([f.timestamp for f in frames]),
        eyeballs=median_eyeballs,
        gazes=median_gazes,
    )


# ---------------------------------------------------------------------------
# Message parsing (called inside the ZMQ thread)
# ---------------------------------------------------------------------------

def _parse_3d_eyeball(eye_id: int, timestamp: float, data: dict) -> Pupil3dEyeballData:
    """Parse a ``pupil.<id>.3d`` msgpack dict into :class:`Pupil3dEyeballData`."""
    sphere = data.get("sphere", {})
    circle_3d = data.get("circle_3d", {})

    sc = sphere.get("center", [0.0, 0.0, 0.0])
    cc = circle_3d.get("center", [0.0, 0.0, 0.0])
    cn = circle_3d.get("normal", [0.0, 0.0, 0.0])

    return Pupil3dEyeballData(
        eye_id=eye_id,
        timestamp=data.get("timestamp", timestamp),
        confidence=data.get("confidence", 0.0),
        sphere_center_x=sc[0] if len(sc) > 0 else 0.0,
        sphere_center_y=sc[1] if len(sc) > 1 else 0.0,
        sphere_center_z=sc[2] if len(sc) > 2 else 0.0,
        sphere_radius=sphere.get("radius", 0.0),
        circle_center_x=cc[0] if len(cc) > 0 else 0.0,
        circle_center_y=cc[1] if len(cc) > 1 else 0.0,
        circle_center_z=cc[2] if len(cc) > 2 else 0.0,
        circle_normal_x=cn[0] if len(cn) > 0 else 0.0,
        circle_normal_y=cn[1] if len(cn) > 1 else 0.0,
        circle_normal_z=cn[2] if len(cn) > 2 else 0.0,
        circle_radius=circle_3d.get("radius", 0.0),
        theta=data.get("theta", 0.0),
        phi=data.get("phi", 0.0),
        pupil_diameter_mm=data.get("diameter_3d", data.get("diameter", 0.0)),
    )


def _parse_gaze(eye_id: int, timestamp: float, data: dict) -> PupilGazeData:
    """Parse a ``gaze.3d.<id>.`` msgpack dict into :class:`PupilGazeData`.

    Handles both monocular topics (where gaze data is at the top level)
    and the binocular ``gaze.3d.01.`` topic where per-eye data is nested
    under ``eye_centers_3d`` / ``gaze_normals_3d`` keyed by ``'0'`` / ``'1'``.
    """
    eye_key = str(eye_id)

    # Try monocular format first (gaze_normal_3d / eye_center_3d at top level)
    gn = data.get("gaze_normal_3d", data.get("gaze_normals_3d", {}).get(eye_key, [0.0, 0.0, 0.0]))
    gp = data.get("gaze_point_3d")

    return PupilGazeData(
        eye_id=eye_id,
        timestamp=data.get("timestamp", timestamp),
        gaze_normal_x=gn[0] if len(gn) > 0 else 0.0,
        gaze_normal_y=gn[1] if len(gn) > 1 else 0.0,
        gaze_normal_z=gn[2] if len(gn) > 2 else 0.0,
        gaze_point_3d_x=gp[0] if gp and len(gp) > 0 else None,
        gaze_point_3d_y=gp[1] if gp and len(gp) > 1 else None,
        gaze_point_3d_z=gp[2] if gp and len(gp) > 2 else None,
    )


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

@dataclass
class PupilLabsManager:
    """Manages the Pupil Capture ZMQ bridge thread.

    Lifecycle::

        manager = PupilLabsManager(config=PupilLabsConfig())
        manager.start_bridge()    # launches ZMQ thread
        ...
        data = manager.get_median_pupil_data()  # called per camera frame
        ...
        manager.stop_bridge()     # joins thread, cleans up ZMQ

    Recording commands are sent via a thread-safe queue so the HTTP
    endpoint (main thread) can trigger recording without touching ZMQ
    sockets from the wrong thread.
    """

    config: PupilLabsConfig

    # -- Thread management --
    _zmq_thread: threading.Thread | None = field(default=None, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)

    # -- Data accumulation --
    _pupil_deque: deque[PupilFramePayload] = field(
        default_factory=deque, repr=False
    )
    _deque_lock: object = field(
        default_factory=threading.Lock, repr=False
    )

    # -- Recording command queue --
    _command_queue: object = field(
        default_factory=queue.SimpleQueue, repr=False
    )

    # -- Status --
    _connected: bool = False
    _recording: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_bridge(self) -> None:
        """Launch the ZMQ bridge thread.

        No-op if the thread is already running. The thread connects to
        Pupil Capture, discovers the SUB port, and begins accumulating
        pupil data into the internal deque.

        Raises:
            RuntimeError: If the thread is already alive.
            ConnectionError: If the discovery handshake fails.
        """
        if self._zmq_thread is not None and self._zmq_thread.is_alive():
            logger.warning("Pupil ZMQ bridge thread is already running")
            return

        self._stop_event.clear()
        self._zmq_thread = threading.Thread(
            target=self._run_zmq_bridge,
            name="PupilZMQBridge",
            daemon=True,
        )
        self._zmq_thread.start()
        logger.info("Pupil ZMQ bridge thread started")

    def stop_bridge(self) -> None:
        """Signal the ZMQ thread to stop and wait for it to exit.

        Safe to call even if the bridge was never started or has already
        been stopped.
        """
        self._stop_event.set()
        if self._zmq_thread is not None and self._zmq_thread.is_alive():
            logger.info("Waiting for Pupil ZMQ bridge thread to exit...")
            self._zmq_thread.join(timeout=5.0)
            if self._zmq_thread.is_alive():
                logger.warning(
                    "Pupil ZMQ bridge thread did not exit within timeout"
                )
            else:
                logger.info("Pupil ZMQ bridge thread exited")
        self._zmq_thread = None
        self._connected = False

    def get_median_pupil_data(self) -> PupilFramePayload | None:
        """Drain accumulated pupil frames and return the per-field median.

        Called from the main thread (via
        :meth:`FreemocapApplication.get_latest_frontend_payloads`) once
        per camera frame. Drains ALL queued frames, computes the median,
        and clears the deque for the next camera frame.

        Returns:
            A :class:`PupilFramePayload` with median values, or ``None``
            if no pupil data has arrived since the last call.
        """
        with self._deque_lock:
            if not self._pupil_deque:
                return None
            frames = list(self._pupil_deque)
            self._pupil_deque.clear()

        try:
            return _compute_median_payload(frames)
        except Exception:
            logger.exception("Failed to compute median pupil payload")
            return None

    def trigger_recording_start(self, recording_path: str) -> None:
        """Tell the ZMQ thread to start Pupil Capture recording.

        Args:
            recording_path: Path to the FreeMoCap recording directory.
                The directory name is used as the Pupil Capture session name.
        """
        import os
        session_name = os.path.basename(recording_path.rstrip("/\\"))
        self._command_queue.put(("start_recording", session_name))
        logger.debug(
            f"Queued recording START command (session={session_name!r})"
        )

    def trigger_recording_stop(self) -> None:
        """Tell the ZMQ thread to stop Pupil Capture recording."""
        self._command_queue.put(("stop_recording", None))
        logger.debug("Queued recording STOP command")

    @property
    def connected(self) -> bool:
        """Whether the ZMQ bridge is connected to Pupil Capture."""
        return self._connected

    @property
    def recording(self) -> bool:
        """Whether Pupil Capture is currently recording."""
        return self._recording

    # ------------------------------------------------------------------
    # ZMQ bridge thread
    # ------------------------------------------------------------------

    def _run_zmq_bridge(self) -> None:
        """Thread target. Connects to Pupil Capture, streams data.

        Runs until ``_stop_event`` is set. All ZMQ socket operations
        happen on this thread — the main thread never touches ZMQ.
        """
        try:
            import zmq
            import msgpack
        except ImportError as e:
            logger.error(
                f"Cannot start Pupil ZMQ bridge — missing dependency: {e}\n"
                "Install with: pip install freemocap[pupil]\n"
                "Or: uv sync --extra pupil"
            )
            return

        from freemocap.core.pupil.pupil_helpers.pupil_capture_api import (
            create_ctrl_socket,
            create_sub_socket,
            discover_sub_port,
            pupil_open_eye_window,
            pupil_start_recording,
            pupil_stop_recording,
        )

        ctx = zmq.Context()
        sub = None
        ctrl = None

        try:
            # -- Discovery --
            try:
                sub_port = discover_sub_port(
                    ctx,
                    host=self.config.pupil_capture_host,
                    port=self.config.pupil_capture_port,
                )
            except zmq.ZMQError as e:
                logger.error(
                    f"Failed to discover Pupil Capture SUB_PORT: {e}\n"
                    "Is Pupil Capture running?"
                )
                return
            except Exception:
                logger.exception("Unexpected error during Pupil Capture discovery")
                return

            # -- Subscribe to data --
            sub = create_sub_socket(
                ctx,
                host=self.config.pupil_capture_host,
                sub_port=sub_port,
                eye_ids=self.config.eye_ids,
            )

            # -- Control socket for recording --
            ctrl = create_ctrl_socket(
                ctx,
                host=self.config.pupil_capture_host,
                port=self.config.pupil_capture_port,
            )

            self._connected = True
            logger.info(
                f"Pupil ZMQ bridge connected to {self.config.pupil_capture_host}"
                f":{sub_port} (config port: {self.config.pupil_capture_port})"
            )

            # -- Open native eye viewer windows --
            if self.config.open_eye_windows:
                for eye_id in self.config.eye_ids:
                    try:
                        pupil_open_eye_window(ctrl, eye_id)
                    except Exception:
                        logger.exception(
                            f"Failed to open eye window for eye {eye_id} "
                            f"(Pupil Capture may not have an eye process for it)"
                        )

            # -- Poll loop --
            poller = zmq.Poller()
            poller.register(sub, zmq.POLLIN)

            # Per-eye accumulation (topics arrive independently)
            eyeball_state: dict[int, Pupil3dEyeballData] = {}
            gaze_state: dict[int, PupilGazeData] = {}

            while not self._stop_event.is_set():
                # --- Handle recording commands ---
                self._drain_command_queue(ctrl, pupil_start_recording, pupil_stop_recording)

                # --- Poll ZMQ (50ms timeout so we check stop_event regularly) ---
                socks = dict(poller.poll(timeout=50))
                if sub not in socks:
                    continue

                topic_bytes, payload_bytes = sub.recv_multipart()
                topic = topic_bytes.decode()
                data: dict = msgpack.unpackb(payload_bytes)
                timestamp = data.get("timestamp", time.time())

                # --- Parse by topic ---
                if topic.startswith("pupil."):
                    # topic format: "pupil.<eye_id>.3d"
                    eye_id = int(topic.split(".")[1])
                    eyeball_state[eye_id] = _parse_3d_eyeball(eye_id, timestamp, data)

                elif topic.startswith("gaze."):
                    # topic format: "gaze.3d.<id>." where id is "0", "1", or "01"
                    gaze_id = topic.split(".")[2]
                    if gaze_id == "01":
                        # Binocular — extract per-eye data from nested dicts
                        for eye_key in ("0", "1"):
                            eye_id = int(eye_key)
                            eye_data = _extract_binocular_eye(data, eye_key, timestamp)
                            if eye_data is not None:
                                gaze_state[eye_id] = eye_data
                    else:
                        # Monocular
                        try:
                            eye_id = int(gaze_id)
                        except ValueError:
                            continue
                        gaze_state[eye_id] = _parse_gaze(eye_id, timestamp, data)

                # --- Emit combined frame ---
                if eyeball_state:
                    frame = PupilFramePayload(
                        timestamp=timestamp,
                        eyeballs=list(eyeball_state.values()),
                        gazes=list(gaze_state.values()),
                    )
                    with self._deque_lock:
                        self._pupil_deque.append(frame)

        except zmq.ZMQError:
            if not self._stop_event.is_set():
                logger.exception("ZMQ error in Pupil bridge thread")
        except Exception:
            logger.exception("Unexpected error in Pupil ZMQ bridge thread")
        finally:
            self._connected = False
            if sub is not None:
                try:
                    sub.close()
                except Exception:
                    pass
            if ctrl is not None:
                try:
                    ctrl.close()
                except Exception:
                    pass
            try:
                ctx.term()
            except Exception:
                pass
            logger.info("Pupil ZMQ bridge thread cleaned up")

    def _drain_command_queue(
        self,
        ctrl_socket,
        pupil_start_recording_fn,
        pupil_stop_recording_fn,
    ) -> None:
        """Process any pending recording commands from the main thread."""
        while True:
            try:
                cmd, arg = self._command_queue.get_nowait()
            except queue.Empty:
                break

            try:
                if cmd == "start_recording":
                    pupil_start_recording_fn(ctrl_socket, recording_name=arg or "")
                    self._recording = True
                elif cmd == "stop_recording":
                    pupil_stop_recording_fn(ctrl_socket)
                    self._recording = False
            except Exception:
                logger.exception(f"Failed to execute Pupil recording command: {cmd}")


def _extract_binocular_eye(
    data: dict, eye_key: str, timestamp: float
) -> PupilGazeData | None:
    """Extract per-eye gaze data from a binocular ``gaze.3d.01.`` message."""
    eye_id = int(eye_key)

    gaze_normals = data.get("gaze_normals_3d", {})
    eye_centers = data.get("eye_centers_3d", {})
    gaze_point = data.get("gaze_point_3d")

    gn = gaze_normals.get(eye_key)
    if gn is None:
        return None

    return PupilGazeData(
        eye_id=eye_id,
        timestamp=data.get("timestamp", timestamp),
        gaze_normal_x=gn[0] if len(gn) > 0 else 0.0,
        gaze_normal_y=gn[1] if len(gn) > 1 else 0.0,
        gaze_normal_z=gn[2] if len(gn) > 2 else 0.0,
        gaze_point_3d_x=gaze_point[0] if gaze_point and len(gaze_point) > 0 else None,
        gaze_point_3d_y=gaze_point[1] if gaze_point and len(gaze_point) > 1 else None,
        gaze_point_3d_z=gaze_point[2] if gaze_point and len(gaze_point) > 2 else None,
    )
