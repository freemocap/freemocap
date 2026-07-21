"""
Telemetry integration for FreeMoCap.

Initializes the skellypings TelemetryClient on startup and sends an `app_opened` event with
anonymous system specifications. Respects the user's opt-in/opt-out choice stored in
telemetry_config.json (written by the Electron UI's Settings/Welcome toggle).

The telemetry secret is injected at CI build time via build_info.py. During local development
the default placeholder sends events as unverified (the server accepts them but stores them
separately).
"""

import logging
import platform
from pathlib import Path

import psutil

import freemocap
from freemocap.build_info import SKELLYPINGS_SECRET, SKELLYPINGS_SERVER_URL
from freemocap.system.default_paths import get_default_freemocap_base_folder_path
from freemocap.system.telemetry.telemetry_config import read_telemetry_enabled
from skellypings import TelemetryClient

logger = logging.getLogger(__name__)

_client: TelemetryClient | None = None


def _get_user_id_file() -> Path:
    return Path(get_default_freemocap_base_folder_path()) / "telemetry_uid"


def _collect_system_specs() -> dict[str, object]:
    """Collect anonymous system specifications."""
    mem = psutil.virtual_memory()
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(mem.total / (1024 ** 3), 1),
    }


def initialize_telemetry() -> None:
    """Start the skellypings telemetry client and send an app_opened event, if enabled."""
    global _client

    if not read_telemetry_enabled():
        logger.info("Skellypings telemetry is disabled by user preference")
        return

    secret_status: str = "CONFIGURED" if SKELLYPINGS_SECRET != "not-configured" else "NOT CONFIGURED (events will be unverified)"
    logger.info(
        "Skellypings telemetry initializing: server_url=%s, secret=%s, app_version=%s",
        SKELLYPINGS_SERVER_URL,
        secret_status,
        freemocap.__version__,
    )

    user_id_file: Path = _get_user_id_file()
    logger.info("Skellypings user_id_file: %s", user_id_file)

    _client = TelemetryClient(
        server_url=SKELLYPINGS_SERVER_URL,
        secret=SKELLYPINGS_SECRET,
        app_name="freemocap",
        app_version=freemocap.__version__,
        user_id_file=user_id_file,
    )

    specs: dict[str, object] = _collect_system_specs()
    logger.info("Skellypings sending 'app_opened' event with payload: %s", specs)
    _client.track("app_opened", payload=specs)
    logger.info(
        "Skellypings telemetry initialized (user_id=%s, flush_interval=%.1fs)",
        _client.user_id,
        _client._flush_interval,
    )


def shutdown_telemetry() -> None:
    """Flush remaining skellypings events and stop the telemetry client."""
    global _client
    if _client is not None:
        logger.info("Skellypings telemetry shutting down, flushing remaining events...")
        _client.shutdown()
        _client = None
        logger.info("Skellypings telemetry shut down")


def track_event(event_type: str, payload: dict[str, object] | None = None) -> None:
    """Track a skellypings telemetry event. No-op if telemetry is disabled."""
    if _client is not None:
        logger.info("Skellypings tracking event: type=%s, payload=%s", event_type, payload)
        _client.track(event_type=event_type, payload=payload)
