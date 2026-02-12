"""Shared calibration file path utilities.

Used by both the anipose and pyceres calibration paths.
"""

from pathlib import Path

from freemocap.system.default_paths import get_default_freemocap_base_folder_path

LAST_SUCCESSFUL_CAMERA_CALIBRATION_STRING = "last_successful_camera_calibration"


def get_calibrations_folder_path() -> Path:
    """Get the main calibrations folder path."""
    return Path(get_default_freemocap_base_folder_path()) / "calibrations"


def create_camera_calibration_file_name(recording_name: str) -> str:
    """Create a standardized camera calibration filename."""
    return f"{recording_name}_camera_calibration.toml"


def get_last_successful_calibration_toml_path() -> Path:
    """Get the path for the last successful calibration TOML file."""
    return get_calibrations_folder_path() / f"{LAST_SUCCESSFUL_CAMERA_CALIBRATION_STRING}.toml"
