"""
Unified application settings: the single serializable state blob
shared between frontend and backend over WebSocket.

Frontend can patch `config` sub-objects via `settings/patch` messages.
Runtime status fields are read-only from the frontend's perspective —
they are set by commands and hardware state changes on the backend.
"""
import asyncio
import logging
from enum import Enum

from pydantic import BaseModel, Field
from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetectorConfig
from skellytracker.trackers.mediapipe_tracker.mediapipe_detector import MediapipeDetectorConfig

from freemocap.core.pipeline.pipeline_configs import (
    CalibrationPipelineConfig,
    MocapPipelineConfig,
    RealtimePipelineConfig,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-models: compose existing configs with runtime status
# ---------------------------------------------------------------------------


class CameraStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class CameraState(BaseModel):
    """Per-camera config + runtime status."""
    config: CameraConfig
    status: CameraStatus = CameraStatus.DISCONNECTED


class PipelineSettings(BaseModel):
    """Realtime pipeline config + runtime status."""
    config: RealtimePipelineConfig | None = None
    is_connected: bool = False
    pipeline_id: str | None = None
    camera_group_id: str | None = None
    is_paused: bool = False


class CalibrationSettings(BaseModel):
    """Calibration config + runtime status."""
    config: CalibrationPipelineConfig = Field(default_factory=CalibrationPipelineConfig)
    is_recording: bool = False
    recording_progress: float = 0.0
    last_recording_path: str | None = None
    has_calibration_toml: bool = False


class MocapSettings(BaseModel):
    """Motion capture config + runtime status."""
    config: MocapPipelineConfig = Field(default_factory=MocapPipelineConfig.default_realtime)
    is_recording: bool = False
    recording_progress: float = 0.0
    last_recording_path: str | None = None


# ---------------------------------------------------------------------------
# Top-level settings blob
# ---------------------------------------------------------------------------


class FreeMoCapSettings(BaseModel):
    """
    The authoritative, serializable application state.

    Sent in full over WebSocket as a `settings/state` message
    whenever any setting or runtime status changes.
    """
    cameras: dict[CameraIdString, CameraState] = Field(default_factory=dict)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    calibration: CalibrationSettings = Field(default_factory=CalibrationSettings)
    mocap: MocapSettings = Field(default_factory=MocapSettings)


# ---------------------------------------------------------------------------
# Settings Manager: owns the state, handles patches, notifies on change
# ---------------------------------------------------------------------------


def _deep_merge(base: dict, patch: dict) -> dict:
    """
    RFC 7396 JSON Merge Patch: recursively merge patch into base.
    Keys in patch overwrite base. Nested dicts merge recursively.
    """
    result = base.copy()
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class SettingsManager:
    """
    Owns the authoritative FreeMoCapSettings instance.

    - Assembles current state from FreemocapApplication on demand.
    - Accepts patches from the frontend, validates, and applies them.
    - Provides an asyncio.Event for WebSocket tasks to await state changes.
    - Maintains a monotonic version counter for ordering.
    """

    def __init__(self) -> None:
        self._settings = FreeMoCapSettings()
        self._version: int = 0
        self._changed = asyncio.Event()

    @property
    def version(self) -> int:
        return self._version

    @property
    def settings(self) -> FreeMoCapSettings:
        return self._settings

    def get_state_message(self) -> dict:
        """Build a `settings/state` WebSocket message."""
        return {
            "message_type": "settings/state",
            "settings": self._settings.model_dump(),
            "version": self._version,
        }

    def notify_changed(self) -> None:
        """Bump version and wake any waiters."""
        self._version += 1
        self._changed.set()

    async def wait_for_change(self) -> None:
        """Block until notify_changed() is called. Clears the event after waking."""
        await self._changed.wait()
        self._changed.clear()

    def apply_patch(self, patch: dict) -> FreeMoCapSettings:
        """
        Apply a partial update (JSON merge-patch) to the current settings.

        Validates the result via Pydantic. If validation fails,
        the settings are left unchanged and the error is raised.
        """
        current = self._settings.model_dump()
        merged = _deep_merge(base=current, patch=patch)
        # Pydantic validates on construction — if this raises, settings are unchanged
        new_settings = FreeMoCapSettings.model_validate(merged)
        self._settings = new_settings
        self.notify_changed()
        logger.info(f"Settings patched (v{self._version}): {list(patch.keys())}")
        return self._settings

    def update_from_app(self, app: "FreemocapApplication") -> None:
        """
        Rebuild settings from the current application state.

        Call this after any command that changes runtime state
        (start recording, connect pipeline, etc.).
        """
        # Camera state
        cameras: dict[CameraIdString, CameraState] = {}
        for camera_group in app.camera_group_manager.camera_groups.values():
            for cam_id, cam_config in camera_group.configs.items():
                cameras[cam_id] = CameraState(
                    config=cam_config,
                    status=CameraStatus.CONNECTED,
                )

        # Pipeline state
        pipeline = PipelineSettings()
        realtime_pipelines = app.realtime_pipeline_manager.pipelines
        if realtime_pipelines:
            # Take the first active pipeline (single-pipeline assumption for now)
            first_pipeline = next(iter(realtime_pipelines.values()))
            pipeline = PipelineSettings(
                config=first_pipeline.config,
                is_connected=first_pipeline.alive,
                pipeline_id=first_pipeline.id,
                camera_group_id=first_pipeline.camera_group.id,
            )

        # Preserve user-set config values that aren't derived from runtime
        calibration = CalibrationSettings(
            config=self._settings.calibration.config,
            is_recording=self._settings.calibration.is_recording,
            recording_progress=self._settings.calibration.recording_progress,
            last_recording_path=self._settings.calibration.last_recording_path,
            has_calibration_toml=self._settings.calibration.has_calibration_toml,
        )

        mocap = MocapSettings(
            config=self._settings.mocap.config,
            is_recording=self._settings.mocap.is_recording,
            recording_progress=self._settings.mocap.recording_progress,
            last_recording_path=self._settings.mocap.last_recording_path,
        )

        self._settings = FreeMoCapSettings(
            cameras=cameras,
            pipeline=pipeline,
            calibration=calibration,
            mocap=mocap,
        )
        self.notify_changed()

    def update_calibration_status(
        self,
        is_recording: bool | None = None,
        recording_progress: float | None = None,
        last_recording_path: str | None = None,
        has_calibration_toml: bool | None = None,
    ) -> None:
        """Update calibration runtime status fields and notify."""
        cal = self._settings.calibration
        if is_recording is not None:
            cal.is_recording = is_recording
        if recording_progress is not None:
            cal.recording_progress = recording_progress
        if last_recording_path is not None:
            cal.last_recording_path = last_recording_path
        if has_calibration_toml is not None:
            cal.has_calibration_toml = has_calibration_toml
        self.notify_changed()

    def update_mocap_status(
        self,
        is_recording: bool | None = None,
        recording_progress: float | None = None,
        last_recording_path: str | None = None,
    ) -> None:
        """Update mocap runtime status fields and notify."""
        moc = self._settings.mocap
        if is_recording is not None:
            moc.is_recording = is_recording
        if recording_progress is not None:
            moc.recording_progress = recording_progress
        if last_recording_path is not None:
            moc.last_recording_path = last_recording_path
        self.notify_changed()