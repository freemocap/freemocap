"""Availability of optional trackers on the backend running this application."""
import importlib.util
import platform
import sys


def mediapipe_unavailable_reason() -> str | None:
    if sys.platform == "darwin" and platform.machine() == "x86_64":
        return "Sorry, MediaPipe is not supported on Intel Macs yet."
    if importlib.util.find_spec("mediapipe") is None:
        return "MediaPipe is not installed in this server."
    return None
