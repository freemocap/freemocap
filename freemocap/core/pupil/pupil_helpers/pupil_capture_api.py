"""Low-level ZMQ helpers for communicating with Pupil Capture's IPC Backbone.

These functions are designed to be called from the ZMQ bridge thread.
They handle the REQ/REP protocol: every send must be followed by a recv
or Pupil Capture may become unresponsive.
"""

import logging

logger = logging.getLogger(__name__)


def discover_sub_port(
    zmq_context,
    host: str = "localhost",
    port: int = 50020,
) -> str:
    """Discover the SUB port from Pupil Capture's IPC Backbone.

    Connects a temporary REQ socket, sends ``"SUB_PORT"``, and returns
    the port number as a string.

    Args:
        zmq_context: A :class:`zmq.Context` instance.
        host: Pupil Capture hostname.
        port: IPC Backbone REQ/REP port (default: 50020).

    Returns:
        The SUB port number as a string (e.g. ``"50021"``).
    """
    import zmq

    req = zmq_context.socket(zmq.REQ)
    try:
        req.connect(f"tcp://{host}:{port}")
        req.send_string("SUB_PORT")
        sub_port = req.recv_string()
        logger.info(f"Discovered Pupil Capture SUB_PORT: {sub_port}")
        return sub_port
    finally:
        req.close()


def create_sub_socket(
    zmq_context,
    host: str = "localhost",
    sub_port: str = "50021",
    eye_ids: list[int] | None = None,
):
    """Create and configure a ZMQ SUB socket subscribed to pupil/gaze topics.

    Args:
        zmq_context: A :class:`zmq.Context` instance.
        host: Pupil Capture hostname.
        sub_port: The SUB port (discovered via :func:`discover_sub_port`).
        eye_ids: Which eyes to subscribe to (default: ``[0, 1]``).

    Returns:
        A configured :class:`zmq.Socket` of type SUB.
    """
    import zmq

    if eye_ids is None:
        eye_ids = [0, 1]

    sub = zmq_context.socket(zmq.SUB)
    sub.connect(f"tcp://{host}:{sub_port}")

    for eye_id in eye_ids:
        # 3D pupil data — eyeball sphere, pupil circle, diameter
        sub.setsockopt_string(zmq.SUBSCRIBE, f"pupil.{eye_id}.3d")
        # Monocular 3D gaze (post-calibration)
        sub.setsockopt_string(zmq.SUBSCRIBE, f"gaze.3d.{eye_id:02d}.")

    # Also subscribe to binocular gaze if available
    sub.setsockopt_string(zmq.SUBSCRIBE, "gaze.3d.01.")

    return sub


def create_ctrl_socket(
    zmq_context,
    host: str = "localhost",
    port: int = 50020,
):
    """Create a ZMQ REQ socket for sending control commands to Pupil Capture.

    Args:
        zmq_context: A :class:`zmq.Context` instance.
        host: Pupil Capture hostname.
        port: IPC Backbone REQ/REP port (default: 50020).

    Returns:
        A configured :class:`zmq.Socket` of type REQ.
    """
    import zmq

    ctrl = zmq_context.socket(zmq.REQ)
    ctrl.connect(f"tcp://{host}:{port}")
    return ctrl


def pupil_start_recording(ctrl_socket, recording_name: str = "") -> str:
    """Send the start-recording command to Pupil Capture.

    Uses the ``"R"`` command. If *recording_name* is provided, it is
    passed as the session name (``"R <name>"``).

    Args:
        ctrl_socket: A ZMQ REQ socket connected to Pupil Capture.
        recording_name: Optional session name for the recording.

    Returns:
        The response string from Pupil Capture.
    """
    if recording_name:
        cmd = f"R {recording_name}"
    else:
        cmd = "R"

    ctrl_socket.send_string(cmd)
    response = ctrl_socket.recv_string()
    logger.info(f"Pupil Capture recording STARTED (name={recording_name!r}): {response}")
    return response


def pupil_stop_recording(ctrl_socket) -> str:
    """Send the stop-recording command to Pupil Capture.

    Uses the ``"r"`` command.

    Args:
        ctrl_socket: A ZMQ REQ socket connected to Pupil Capture.

    Returns:
        The response string from Pupil Capture.
    """
    ctrl_socket.send_string("r")
    response = ctrl_socket.recv_string()
    logger.info(f"Pupil Capture recording STOPPED: {response}")
    return response


def pupil_open_eye_window(ctrl_socket, eye_id: int) -> str:
    """Send a notification to open Pupil Capture's native eye camera viewer.

    Sends an ``eye_process.should_start.<eye_id>`` notification via the
    REQ socket. Pupil Capture will pop open its eye window with the live
    camera feed and pupil detection overlay.

    Uses the two-part notification format: topic string (SNDMORE) followed
    by a msgpack-encoded dict with the ``subject`` key.

    Args:
        ctrl_socket: A ZMQ REQ socket connected to Pupil Capture.
        eye_id: Which eye to open: ``0`` (right) or ``1`` (left).

    Returns:
        The response string from Pupil Capture (``"Notification received"``).
    """
    import zmq
    import msgpack

    subject = f"eye_process.should_start.{eye_id}"
    notification = {"subject": subject, "eye_id": eye_id}
    payload = msgpack.dumps(notification)

    ctrl_socket.send_string(f"notify.{subject}", flags=zmq.SNDMORE)
    ctrl_socket.send(payload)
    response = ctrl_socket.recv_string()
    logger.info(f"Pupil Capture eye window opened (eye {eye_id}): {response}")
    return response
