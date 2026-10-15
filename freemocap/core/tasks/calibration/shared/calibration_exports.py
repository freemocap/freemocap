"""Export changed posthoc camera geometry without rewriting its source calibration."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from filelock import FileLock

from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_toml import CalibrationToml
from freemocap.core.tasks.calibration.shared.calibration_transform import CalibrationTransform

logger = logging.getLogger(__name__)

def save_aligned_calibration(*, source_path: Path, source: CalibrationResult,
                            recording_path: Path, transformations: tuple[CalibrationTransform, ...],
                            recording_id: str, run_id: int = 0) -> Path | None:
    """Save only changed geometry; reuse an identical validated export on reruns.

    The source is the in-memory snapshot actually used for reconstruction. No
    rounding/tolerance is used to discard small scientific changes. The original
    calibration and the explicit apply-transforms UI remain separate from this
    derived export. Names preserve the source stem and UTC creation time.
    """
    if not transformations:
        return None
    aligned = source.transformed(transformations=transformations, recording_id=recording_id)
    if aligned.cameras == source.cameras:
        return None
    # Compare the authoritative file-format fields. Loading CameraModel also
    # derives rotation representations, whose round-off is not a file change.
    payload = CalibrationToml.from_calibration(cameras=aligned.cameras,
        metadata=aligned.to_metadata()).model_dump(mode="json", by_alias=True, exclude_none=True)
    fingerprint = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
    folder = recording_path / "exports" / "calibration_copies"
    if run_id != 0:
        folder = recording_path / "exports" / f"run-{run_id}" / "calibration_copies"
    folder.mkdir(parents=True, exist_ok=True)
    suffix = f".run-{run_id}" if run_id != 0 else ""
    # Serialize simultaneous saves and compare content, not just the short hash.
    with FileLock(str(folder / ".calibration-export.lock")):
        for candidate in folder.iterdir():
            if candidate.name.startswith(source_path.stem + "__aligned__") and candidate.name.endswith(f"__{fingerprint}{suffix}.toml"):
                if CalibrationToml.model_validate_toml_file(candidate).model_dump(mode="json", by_alias=True, exclude_none=True) == payload:
                    logger.info("Reusing unchanged aligned calibration export: %s", candidate)
                    return candidate
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S-%fZ")
        destination = folder / f"{source_path.stem}__aligned__{timestamp}__{fingerprint}{suffix}.toml"
        with NamedTemporaryFile(dir=folder, prefix=".calibration-", suffix=".toml", delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            aligned.save_toml(temporary_path)
            if CalibrationToml.model_validate_toml_file(temporary_path).model_dump(mode="json", by_alias=True, exclude_none=True) != payload:
                raise ValueError("Aligned calibration export did not preserve calibration data")
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)
        logger.info("Saved changed camera calibration: %s (source unchanged: %s)", destination, source_path)
        return destination
