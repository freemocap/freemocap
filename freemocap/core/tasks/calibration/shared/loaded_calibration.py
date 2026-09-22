"""A validated calibration loaded from a saved file."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from freemocap.core.tasks.calibration.shared.calibration_metadata import CalibrationMetadata
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


class LoadedCalibration(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    path: Path
    mtime_ms: float = Field(alias="mtimeMs")
    cameras: list[CameraModel]
    metadata: CalibrationMetadata

    @classmethod
    def from_path(cls, path: Path) -> "LoadedCalibration":
        resolved_path = path.expanduser().resolve()
        calibration = CalibrationResult.load_toml(resolved_path)
        return cls(
            path=resolved_path,
            mtime_ms=resolved_path.stat().st_mtime_ns / 1_000_000,
            cameras=calibration.cameras,
            metadata=calibration.to_metadata(),
        )
