"""
Telemetry opt-in/out configuration, stored at <freemocap_base_folder>/telemetry_config.json.

    { "telemetry_enabled": true }

The Electron UI writes this file (the Settings / Welcome opt-out toggle); the Python backend
reads it here. Both sides resolve the base folder the same way, so they agree on the path.
"""

import json
import logging
from pathlib import Path

from freemocap.system.default_paths import get_default_freemocap_base_folder_path

logger = logging.getLogger(__name__)

TELEMETRY_CONFIG_FILENAME: str = "telemetry_config.json"


def _get_telemetry_config_path() -> Path:
    return Path(get_default_freemocap_base_folder_path()) / TELEMETRY_CONFIG_FILENAME


def read_telemetry_enabled() -> bool:
    """Read telemetry opt-in status. Defaults to True if no config file exists."""
    config_path = _get_telemetry_config_path()
    if not config_path.exists():
        # First launch: default to enabled, write the file so the UI can read it back
        write_telemetry_enabled(enabled=True)
        return True

    try:
        data = json.loads(config_path.read_text())
        return bool(data.get("telemetry_enabled", True))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read telemetry config, defaulting to enabled: %s", e)
        return True


def write_telemetry_enabled(enabled: bool) -> None:
    """Write telemetry opt-in status."""
    config_path = _get_telemetry_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps({"telemetry_enabled": enabled}, indent=2) + "\n")
