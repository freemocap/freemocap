"""Application names for Tracker-owned keypoint schemas."""
from pydantic import BaseModel
from skellytracker.core.io.tracker_profiles import tracker_profile

class TrackerDefinition(BaseModel):
    name: str
    tracked_points: tuple[str, ...]
    connections: tuple[tuple[str, str], ...]

def tracker_definition(detector_type: str) -> TrackerDefinition:
    profile = tracker_profile(detector_type)
    # Preserve existing recording source identifiers.
    saved_name = {"rtmpose": "rtmpose_wholebody", "mediapipe": "mediapipe_wholebody"}.get(detector_type, profile.name)
    return TrackerDefinition(name=saved_name, tracked_points=profile.keypoint_names, connections=profile.connections)

RTMPOSE_WHOLEBODY_DEFINITION = tracker_definition("rtmpose")
MEDIAPIPE_WHOLEBODY_DEFINITION = tracker_definition("mediapipe")
COMBINED_WHOLEBODY_DEFINITION = tracker_definition("rtmw_mediapipe_hands")
