import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from freemocap.system.telemetry.telemetry import track_event

logger = logging.getLogger(__name__)
telemetry_router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


class TelemetryEventRequest(BaseModel):
    event_type: str = Field(
        alias="eventType",
        description="Event name, e.g. 'tour_started' or 'tour_step_viewed'.",
    )
    payload: dict[str, object] | None = Field(
        default=None,
        description="Optional anonymous event properties (no PII).",
    )


@telemetry_router.post("/track", summary="Record an anonymous telemetry event")
def track_telemetry_event(request: TelemetryEventRequest) -> dict[str, bool]:
    """Forward a UI-originated event to the telemetry client.

    This is a no-op when the user has opted out of telemetry: track_event only
    forwards to the skellypings client when it was initialized, which happens
    solely when telemetry is enabled. The opt-in decision therefore lives in one
    place (telemetry_config.json) and the UI does not need to re-check it.
    """
    track_event(event_type=request.event_type, payload=request.payload)
    return {"ok": True}
