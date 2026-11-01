"""Application-facing access to Tracker-owned schemas and mapping selection."""
from pathlib import Path
from skellytracker.core.io.tracker_profiles import tracker_profile
from skellytracker.core.io.composite_tracker_mapping import CompositeTrackerMapping

def body_mapping_yaml_path(detector_type: str) -> Path:
    return tracker_profile(detector_type).mapping_paths[0]

def hand_mapping_yaml_path(detector_type: str) -> Path:
    return tracker_profile(detector_type).mapping_paths[1]

def tracker_keypoint_names(detector_type: str) -> tuple[str, ...]:
    """Publish Tracker's declared keypoints in Core's established sorted channel order."""
    return tuple(sorted(tracker_profile(detector_type).keypoint_names))

def load_standard_human_mapping(detector_type: str) -> CompositeTrackerMapping:
    return tracker_profile(detector_type).load_mapping()
