"""
VMC (Virtual Motion Capture) protocol sender.

Broadcasts rigid body segment poses over OSC/UDP using the VMC protocol,
enabling real-time streaming to VTuber apps (VSeeFace, VMagicMirror),
game engines (Unity, Unreal), and other VMC-compatible receivers.

Protocol reference:
    https://protocol.vmc.info/english

VMC bone transforms are sent as:
    /VMC/Ext/Bone/Pos  <name> <px> <py> <pz> <qx> <qy> <qz> <qw>

The sender maps freemocap's mediapipe bone keys ("parent->child") to
VRM humanoid bone names ("LeftUpperArm", "RightLowerLeg", etc.).

Coordinate system conversion:
    freemocap: right-handed, Y-up (after the 180° X rotation)
    VMC/Unity: left-handed, Y-up
    Conversion: negate X position and negate X/Z quaternion components.

Usage:
    sender = VMCSender(host="127.0.0.1", port=39539)
    sender.send(rigid_body_poses)
    sender.close()
"""

import logging
import socket
import struct

from freemocap.core.mocap.skeleton_dewiggler.dewiggling_methods.rigid_body_estimator import RigidBodyPose

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mediapipe bone key → VRM humanoid bone name mapping
# ---------------------------------------------------------------------------

MEDIAPIPE_TO_VRM: dict[str, str] = {
    # Arms
    "left_shoulder->left_elbow": "LeftUpperArm",
    "left_elbow->left_wrist": "LeftLowerArm",
    "right_shoulder->right_elbow": "RightUpperArm",
    "right_elbow->right_wrist": "RightLowerArm",
    # Legs
    "left_hip->left_knee": "LeftUpperLeg",
    "left_knee->left_ankle": "LeftLowerLeg",
    "right_hip->right_knee": "RightUpperLeg",
    "right_knee->right_ankle": "RightLowerLeg",
    # Feet
    "left_ankle->left_foot_index": "LeftFoot",
    "left_ankle->left_heel": "LeftToes",
    "right_ankle->right_foot_index": "RightFoot",
    "right_ankle->right_heel": "RightToes",
}


# ---------------------------------------------------------------------------
# Minimal OSC message builder (avoids dependency on python-osc)
# ---------------------------------------------------------------------------


def _osc_string(s: str) -> bytes:
    """Encode a string as an OSC string (null-terminated, padded to 4 bytes)."""
    encoded = s.encode("utf-8") + b"\x00"
    # Pad to multiple of 4 bytes
    padding = (4 - len(encoded) % 4) % 4
    return encoded + b"\x00" * padding


def _osc_float(f: float) -> bytes:
    """Encode a float as an OSC float32."""
    return struct.pack(">f", f)


def _build_bone_message(
    bone_name: str,
    px: float,
    py: float,
    pz: float,
    qx: float,
    qy: float,
    qz: float,
    qw: float,
) -> bytes:
    """Build a single /VMC/Ext/Bone/Pos OSC message."""
    address = _osc_string("/VMC/Ext/Bone/Pos")
    type_tag = _osc_string(",sfffffff")
    payload = (
        _osc_string(bone_name)
        + _osc_float(px)
        + _osc_float(py)
        + _osc_float(pz)
        + _osc_float(qx)
        + _osc_float(qy)
        + _osc_float(qz)
        + _osc_float(qw)
    )
    return address + type_tag + payload


def _build_bundle(messages: list[bytes], timetag: int = 1) -> bytes:
    """Build an OSC bundle containing multiple messages."""
    header = _osc_string("#bundle")
    time_bytes = struct.pack(">Q", timetag)  # NTP "immediately"
    elements = b""
    for msg in messages:
        elements += struct.pack(">I", len(msg)) + msg
    return header + time_bytes + elements


# ---------------------------------------------------------------------------
# VMC Sender
# ---------------------------------------------------------------------------


class VMCSender:
    """Broadcasts rigid body poses over VMC (OSC/UDP).

    Converts freemocap's right-handed Y-up coordinates to VMC/Unity's
    left-handed Y-up coordinates by negating X position and X/Z quaternion
    components.
    """

    def __init__(self, *, host: str, port: int) -> None:
        self._host: str = host
        self._port: int = port
        self._socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(False)
        logger.info(f"VMCSender initialized: {host}:{port}")

    def send(self, rigid_body_poses: dict[str, RigidBodyPose]) -> None:
        """Send all mappable rigid body poses as a VMC OSC bundle.

        Bones without a VRM mapping are silently skipped.
        """
        messages: list[bytes] = []

        for bone_key, pose in rigid_body_poses.items():
            vrm_name = MEDIAPIPE_TO_VRM.get(bone_key)
            if vrm_name is None:
                continue

            px, py, pz = pose.position
            qw, qx, qy, qz = pose.orientation

            # Right-handed → left-handed conversion: negate X pos and X/Z quat
            msg = _build_bone_message(
                bone_name=vrm_name,
                px=-px,
                py=py,
                pz=pz,
                qx=-qx,
                qy=qy,
                qz=-qz,
                qw=qw,
            )
            messages.append(msg)

        if not messages:
            return

        bundle = _build_bundle(messages)
        try:
            self._socket.sendto(bundle, (self._host, self._port))
        except OSError as e:
            # UDP send failures are non-fatal (receiver might not be running)
            logger.debug(f"VMC send failed: {e}")

    def close(self) -> None:
        """Close the UDP socket."""
        self._socket.close()
        logger.info(f"VMCSender closed: {self._host}:{self._port}")
