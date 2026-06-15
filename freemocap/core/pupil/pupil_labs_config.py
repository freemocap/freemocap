"""Pydantic configuration model for the Pupil Labs integration."""

from pydantic import BaseModel, Field


class PupilLabsConfig(BaseModel):
    """Configuration for connecting to Pupil Capture's IPC backbone.

    These values are set via the HTTP endpoint and used by the
    :class:`PupilLabsManager` when starting the ZMQ bridge thread.
    """

    pupil_capture_host: str = Field(
        default="localhost",
        description="Hostname where Pupil Capture is running",
    )
    pupil_capture_port: int = Field(
        default=50020,
        description="Port for the REQ/REP discovery handshake (IPC Backbone default: 50020)",
    )
    eye_ids: list[int] = Field(
        default=[0, 1],
        description="Which eyes to track: 0 = right, 1 = left",
    )
    open_eye_windows: bool = Field(
        default=True,
        description="If True, automatically open Pupil Capture's native eye camera "
                    "viewer windows on connect (sends eye_process.should_start notifications)",
    )
