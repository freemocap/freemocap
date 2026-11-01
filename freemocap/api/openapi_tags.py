"""Ordered capability headings for the public HTTP interface."""

OPENAPI_TAGS = [
    {'name': 'App', 'description': 'Server health and lifecycle.'},
    {'name': 'Recordings', 'description': 'Recording discovery, identity and resource availability.'},
    {'name': 'Recording results', 'description': 'Saved runs, channel definitions and recording files.'},
    {'name': 'Recording media', 'description': 'Recorded and derived videos, timelines and byte delivery.'},
    {'name': 'Recording calibration', 'description': 'Calibration associated with a recording.'},
    {'name': 'Playback', 'description': 'Rendering projections for client-controlled playback.'},
    {'name': 'Recording exports', 'description': 'Export selections, published files and export creation.'},
    {'name': 'Recording processing', 'description': 'Processing requests for saved recordings.'},
    {'name': 'Tasks', 'description': 'Accepted work, progress, results and cancellation.'},
    {'name': 'Capture', 'description': 'Start and stop recording from connected cameras.'},
    {'name': 'Recording import', 'description': 'Inspect, synchronize and import external media.'},
    {'name': 'Realtime processing', 'description': 'Configure and control live processing.'},
    {'name': 'Calibration tools', 'description': 'Discover, inspect and transform calibration files.'},
    {'name': 'Blender', 'description': 'Blender executable and package operations.'},
    {'name': 'Cameras', 'description': 'Standalone SkellyCam camera and microphone control.'},
    {'name': 'ONNX', 'description': 'Advertised execution providers and loaded inference-session diagnostics.'},
    {'name': 'FFmpeg', 'description': 'FFmpeg executable discovery.'},
    {'name': 'Telemetry', 'description': 'Application telemetry events.'},
]
