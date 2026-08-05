"""Derive a recording's true framerate from the timestamps written alongside its videos.

`FilterConfig.sampling_rate` defaults to 30.0 and nothing ever set it from the actual
recording, so the post-processing Butterworth low-pass was designed against a framerate
the capture never had. The cutoff scales with that error: a nominal 6 Hz cutoff becomes
`6 * true_fps / 30` in reality. At 31 fps that is a mild 6.2 Hz; at 60 fps it is 12 Hz,
which lets through most of the noise the filter exists to remove.

The per-camera fps reported by the video containers cannot be used for this - the four
cameras in a synchronized recording disagree with each other (34.28 / 34.48 / 34.66 /
34.74 in one measured take) while sharing an identical frame count, because those values
describe each camera's own nominal rate rather than the synchronized multiframe rate.
The multiframe timestamps are the only record of the rate the frames actually share.
"""
import csv
import logging
import statistics
from pathlib import Path

logger = logging.getLogger(__name__)

# Recordings vary in layout between versions, so search rather than assume one path.
_TIMESTAMP_GLOBS = (
    "synchronized_videos/timestamps/*_timestamps.csv",
    "synchronized_videos/timestamps/**/*timestamps.csv",
)
_DURATION_COLUMN_HINT = "frame_duration"
_MIN_SAMPLES = 10
# Anything outside this is more likely a parsing error than a real capture rate.
_PLAUSIBLE_FPS = (1.0, 1000.0)


def _find_timestamp_csv(recording_path: Path) -> Path | None:
    for pattern in _TIMESTAMP_GLOBS:
        for candidate in sorted(recording_path.glob(pattern)):
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
    return None


def _median_frame_duration_ms(csv_path: Path) -> float | None:
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return None
        columns = [c for c in reader.fieldnames if _DURATION_COLUMN_HINT in c]
        if not columns:
            return None
        column = columns[0]
        durations = []
        for row in reader:
            try:
                value = float(row[column])
            except (TypeError, ValueError):
                continue
            if value > 0:
                durations.append(value)
    if len(durations) < _MIN_SAMPLES:
        return None
    # Median, not mean: dropped frames produce double-length intervals that would
    # drag a mean downward and understate the true rate.
    return statistics.median(durations)


def get_recording_framerate(recording_path: str | Path) -> float | None:
    """Return the recording's median framerate in fps, or None if it cannot be determined.

    Returns None rather than a default so callers can decide whether to fall back or
    fail - silently substituting a plausible-looking number is what caused the original
    bug this function exists to fix.
    """
    recording_path = Path(recording_path)
    csv_path = _find_timestamp_csv(recording_path)
    if csv_path is None:
        logger.warning(f"No timestamps CSV found under {recording_path}; cannot determine framerate")
        return None

    median_ms = _median_frame_duration_ms(csv_path)
    if median_ms is None or median_ms <= 0:
        logger.warning(f"Could not read usable frame durations from {csv_path}")
        return None

    framerate = 1000.0 / median_ms
    low, high = _PLAUSIBLE_FPS
    if not (low <= framerate <= high):
        logger.warning(f"Derived implausible framerate {framerate:.2f} fps from {csv_path}; ignoring")
        return None

    logger.info(f"Derived recording framerate: {framerate:.3f} fps (from {csv_path.name})")
    return framerate
