from pathlib import Path

from freemocap.core.tasks.calibration.shared.calibration_toml import CalibrationToml
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.utilities.toml_mixin import TomlMixin
from pydantic import ConfigDict
from freemocap.core.tasks.calibration.shared.calibration_metadata import CalibrationMetadata


class CalibrationResult(CalibrationMetadata, TomlMixin):
    """Output of calibration.

    Serializes to/from calibration TOML. Triangulator
    construction lives in ``freemocap.core.tasks.triangulation.triangulator``.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    cameras: list[CameraModel]

    def to_metadata(self) -> CalibrationMetadata:
        return CalibrationMetadata(**{
            name: getattr(self, name)
            for name in CalibrationMetadata.model_fields
        })

    @property
    def camera_ids(self) -> list[str]:
        return [c.id for c in self.cameras]

    def get_camera(self, camera_id: str) -> CameraModel:
        """Look up a camera by name."""
        for cam in self.cameras:
            if cam.id == camera_id:
                return cam
        raise KeyError(f"Camera '{camera_id}' not found. Available: {self.camera_ids}")

    def save_toml(
            self,
            path: Path,
    ) -> None:
        """Write calibration TOML using the shared file-format model."""
        CalibrationToml.from_calibration(
            cameras=self.cameras, metadata=self.to_metadata(),
        ).model_dump_toml_file(Path(path))

    @classmethod
    def load_toml(cls, path: Path) -> "CalibrationResult":
        """Load calibration TOML through the shared validated file-format model."""
        document = CalibrationToml.model_validate_toml_file(Path(path))
        return cls(
            cameras=document.to_cameras(),
            **document.metadata.model_dump(round_trip=True),
        )
