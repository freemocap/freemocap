"""Compatibility imports; recording read ownership is shared across capabilities."""
from freemocap.api.http.recordings.recording_access import (
    RecordingReadRoute as RecordingPlaybackRoute,
    RecordingResponse as PlaybackResponse,
)
__all__ = ['RecordingPlaybackRoute', 'PlaybackResponse']
