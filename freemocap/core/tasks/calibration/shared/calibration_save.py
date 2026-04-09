"""Shared calibration-file save logic.

Both the anipose and pyceres paths save calibration results to three locations:
  1. The recording folder
  2. The main calibrations folder
  3. The 'last successful' calibration path

This module provides a single function to handle all three.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from freemocap.core.tasks.calibration.shared.calibration_paths import create_camera_calibration_file_name, \
    get_calibrations_folder_path, get_last_successful_calibration_toml_path

logger = logging.getLogger(__name__)


def save_calibration_copies(
    *,
    save_fn: Callable[[Path], None],
    recording_name: str,
    recording_folder_path: str | Path,
) -> Path:
    """Save a calibration to all three standard locations.

    Args:
        save_fn: Callable that writes the calibration data to a given path.
        recording_name: Name of the recording (used to build the filename).
        recording_folder_path: Path to the recording folder.

    Returns:
        Path to the calibration file in the recording folder (primary copy).
    """
    filename = create_camera_calibration_file_name(recording_name=recording_name)

    recording_toml = Path(recording_folder_path) / filename
    save_fn(recording_toml)
    logger.info(f"Saved calibration to recording folder: {recording_toml}")

    calibration_folder_toml = get_calibrations_folder_path() / filename
    save_fn(calibration_folder_toml)
    logger.info(f"Saved calibration to calibrations folder: {calibration_folder_toml}")

    last_successful = get_last_successful_calibration_toml_path()
    save_fn(last_successful)
    logger.info(f"Saved as last successful calibration: {last_successful}")

    return recording_toml
