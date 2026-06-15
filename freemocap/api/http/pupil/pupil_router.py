"""HTTP endpoints for Pupil Labs eye tracker integration.

Provides connect/disconnect/status endpoints for the Pupil Capture
ZMQ bridge. Follows the same pattern as the Blender router.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from freemocap.app.freemocap_application import get_freemocap_app

logger = logging.getLogger(__name__)

pupil_router = APIRouter(prefix="/pupil", tags=["Pupil Labs"])


# ==================== Request/Response Models ====================


class PupilConnectRequest(BaseModel):
    """Request to connect to Pupil Capture and start the ZMQ bridge."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "pupilCaptureHost": "localhost",
                "pupilCapturePort": 50020,
                "eyeIds": [0, 1],
            }
        },
    )
    pupil_capture_host: str = Field(
        default="localhost", alias="pupilCaptureHost"
    )
    pupil_capture_port: int = Field(
        default=50020, alias="pupilCapturePort"
    )
    eye_ids: list[int] = Field(
        default=[0, 1], alias="eyeIds"
    )


class PupilConnectResponse(BaseModel):
    success: bool
    message: str | None = None


class PupilStatusResponse(BaseModel):
    connected: bool
    recording: bool


# ==================== Endpoints ====================


@pupil_router.post("/connect")
def connect_to_pupil(request: PupilConnectRequest) -> PupilConnectResponse:
    """Discover Pupil Capture and start streaming 3D pupil data.

    The ZMQ bridge runs in a background daemon thread. Pupil data will
    appear in the ``pupil_data`` field of subsequent ``frontend_payload``
    WebSocket messages.
    """
    app = get_freemocap_app()
    manager = app.pupil_labs_manager

    # Apply configuration from the request
    manager.config.pupil_capture_host = request.pupil_capture_host
    manager.config.pupil_capture_port = request.pupil_capture_port
    manager.config.eye_ids = request.eye_ids

    try:
        manager.start_bridge()
        return PupilConnectResponse(
            success=True,
            message=f"Connected to Pupil Capture at {request.pupil_capture_host}:{request.pupil_capture_port}",
        )
    except Exception as e:
        logger.exception("Failed to connect to Pupil Capture")
        raise HTTPException(status_code=503, detail=str(e))


@pupil_router.post("/disconnect")
def disconnect_from_pupil() -> PupilConnectResponse:
    """Stop the ZMQ bridge and disconnect from Pupil Capture."""
    try:
        get_freemocap_app().pupil_labs_manager.stop_bridge()
        return PupilConnectResponse(
            success=True, message="Disconnected from Pupil Capture"
        )
    except Exception as e:
        logger.exception("Error disconnecting from Pupil Capture")
        raise HTTPException(status_code=500, detail=str(e))


@pupil_router.get("/status")
def get_pupil_status() -> PupilStatusResponse:
    """Get the current Pupil Capture connection and recording status."""
    manager = get_freemocap_app().pupil_labs_manager
    return PupilStatusResponse(
        connected=manager.connected,
        recording=manager.recording,
    )
