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

skellycam already computes this median for its `*_stats.json` report, so that's tried
first - it's a single field read instead of a full CSV re-parse. Older recordings (and,
until skellycam's `RecordingTimestampsStats.to_json` bug is fixed, current ones too) can
have an empty stats.json, so the CSV median below remains as a fallback.
"""
import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Recordings vary in layout between versions, so search rather than assume one path.
_TIMESTAMP_GLOBS = (
    "synchronized_videos/timestamps/*_timestamps.csv",
    "synchronized_videos/timestamps/**/*timestamps.csv",
)
_STATS_JSON_GLOBS = (
    "synchronized_videos/timestamps/*_stats.json",
    "synchronized_videos/timestamps/**/*stats.json",
)
# Fixed by skellycam's MULTI_FRAME_TIMESTAMP_CSV_ROW dtype - the same column
# skellycam's own framerate_stats.median in *_stats.json is computed from.
_FRAMERATE_COLUMN = "from_previous.framerate.hz"
_MIN_SAMPLES = 10
# Anything outside this is more likely a parsing error than a real capture rate.
_PLAUSIBLE_FPS = (1.0, 1000.0)


def _find_timestamp_csv(recording_path: Path) -> Path | None:
    for pattern in _TIMESTAMP_GLOBS:
        for candidate in sorted(recording_path.glob(pattern)):
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
    return None


def _find_stats_json(recording_path: Path) -> Path | None:
    for pattern in _STATS_JSON_GLOBS:
        for candidate in sorted(recording_path.glob(pattern)):
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
    return None


def _framerate_from_stats_json(recording_path: Path) -> tuple[float, Path] | None:
    json_path = _find_stats_json(recording_path)
    if json_path is None:
        return None

    try:
        stats = json.loads(json_path.read_text())
    except (OSError, json.JSONDecodeError):
        logger.warning(f"Could not parse {json_path}; falling back to CSV")
        return None

    median = stats.get("framerate_stats", {}).get("median")
    if median is None:
        # Empty until skellycam's RecordingTimestampsStats.to_json bug is fixed;
        # not an error, just means this recording needs the CSV fallback.
        return None

    return float(median), json_path


def _median_framerate_from_csv(csv_path: Path) -> float | None:
    values = pd.read_csv(csv_path, usecols=[_FRAMERATE_COLUMN])[_FRAMERATE_COLUMN].dropna()
    values = values[values > 0]
    if len(values) < _MIN_SAMPLES:
        return None
    # Median, not mean: dropped frames produce double-length intervals that would
    # drag a mean downward and understate the true rate.
    return float(values.median())


def get_recording_framerate(recording_path: str | Path) -> float | None:
    """Return the recording's median framerate in fps, or None if it cannot be determined.

    Returns None rather than a default so callers can decide whether to fall back or
    fail - silently substituting a plausible-looking number is what caused the original
    bug this function exists to fix.
    """
    recording_path = Path(recording_path)

    from_json = _framerate_from_stats_json(recording_path)
    if from_json is not None:
        framerate, json_path = from_json
        low, high = _PLAUSIBLE_FPS
        if low <= framerate <= high:
            logger.info(f"Derived recording framerate: {framerate:.3f} fps (from {json_path.name})")
            return framerate
        logger.warning(f"Derived implausible framerate {framerate:.2f} fps from {json_path}; falling back to CSV")

    csv_path = _find_timestamp_csv(recording_path)
    if csv_path is None:
        logger.warning(f"No timestamps CSV found under {recording_path}; cannot determine framerate")
        return None

    framerate = _median_framerate_from_csv(csv_path)
    if framerate is None:
        logger.warning(f"Could not read usable framerates from {csv_path}")
        return None

    low, high = _PLAUSIBLE_FPS
    if not (low <= framerate <= high):
        logger.warning(f"Derived implausible framerate {framerate:.2f} fps from {csv_path}; ignoring")
        return None

    logger.info(f"Derived recording framerate: {framerate:.3f} fps (from {csv_path.name})")
    return framerate
