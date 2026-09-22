"""Explicit, transactional updates to a selected calibration file."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_transform import CalibrationTransform
from freemocap.core.tasks.calibration.shared.loaded_calibration import LoadedCalibration


class CalibrationFileChangedError(ValueError):
    """The selected calibration changed after the client loaded it."""


def _require_revision(path: Path, expected_mtime_ms: float) -> None:
    if path.stat().st_mtime_ns / 1_000_000 != expected_mtime_ms:
        raise CalibrationFileChangedError("Calibration changed on disk; reload it before saving.")


@dataclass(frozen=True, slots=True, kw_only=True)
class PreparedCalibrationUpdate:
    path: Path
    expected_mtime_ms: float
    calibration: CalibrationResult

    def commit(self) -> LoadedCalibration:
        """Commit while the request's preparation context holds the file lock."""
        _require_revision(self.path, self.expected_mtime_ms)
        with NamedTemporaryFile(
            dir=self.path.parent, prefix=f".{self.path.stem}-",
            suffix=".toml", delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            self.calibration.save_toml(temporary_path)
            response = LoadedCalibration(
                path=self.path,
                mtime_ms=temporary_path.stat().st_mtime_ns / 1_000_000,
                cameras=self.calibration.cameras,
                metadata=self.calibration.to_metadata(),
            )
            _require_revision(self.path, self.expected_mtime_ms)
            os.replace(temporary_path, self.path)
            return response
        finally:
            temporary_path.unlink(missing_ok=True)


class CalibrationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: Path
    expected_mtime_ms: FiniteFloat
    transformations: tuple[CalibrationTransform, ...] = Field(min_length=1)
    recording_id: str | None = None

    def save(self) -> LoadedCalibration:
        """Save an explicit update when no realtime pipeline owns the file."""
        with self.prepare() as prepared:
            return prepared.commit()

    @contextmanager
    def prepare(self) -> Iterator[PreparedCalibrationUpdate]:
        """Prepare new geometry without changing the file or interpreting history.

        The caller can prepare replacement runtime objects before committing.
        Leaving this context without calling commit changes no calibration data.
        """
        path = self.path.expanduser().resolve(strict=True)
        with FileLock(str(path) + ".lock", timeout=0):
            _require_revision(path, self.expected_mtime_ms)
            source = CalibrationResult.load_toml(path)
            transformed = source.transformed(
                transformations=self.transformations,
                recording_id=self.recording_id,
            )
            yield PreparedCalibrationUpdate(
                path=path,
                expected_mtime_ms=self.expected_mtime_ms,
                calibration=transformed,
            )
