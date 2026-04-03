"""Camera identity: extract and match camera IDs across recordings.

Camera IDs are the stable link between calibration and future recordings.
They must survive the round-trip: hardware → video filename → calibration TOML → triangulation.

The canonical camera ID comes from CameraConfig.camera_id (a CameraIdString like "000").
Video filenames are expected to encode this ID in a parseable way.
"""

import logging
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

logger = logging.getLogger(__name__)

# Patterns to try, in priority order, when extracting a camera ID from a filename.
# Each pattern should have a single capture group for the camera ID.
_CAMERA_ID_PATTERNS: list[re.Pattern[str]] = [
    # "rec1_camera_000.mp4" or "recording_camera_12.avi"
    re.compile(r"camera[_\-](\d+)", re.IGNORECASE),
    # "rec1_cam000.mp4"
    re.compile(r"cam(\d+)", re.IGNORECASE),
    # "000.mp4" — bare numeric filename (common in freemocap recordings)
    re.compile(r"^(\d+)\.[a-zA-Z0-9]+$"),
]


def extract_camera_id_from_filename(video_path: Path | str) -> str | None:
    """Try to extract a camera ID from a video filename.

    Returns the extracted camera ID string, or None if no pattern matched.
    """
    filename = Path(video_path).name

    for pattern in _CAMERA_ID_PATTERNS:
        match = pattern.search(filename)
        if match:
            return match.group(1)

    return None


def camera_ids_from_video_paths(
    video_paths: list[Path | str],
) -> dict[str, Path]:
    """Extract camera IDs from a list of video paths.

    Returns a dict mapping camera_id → video_path.

    If camera IDs can be extracted from filenames, those are used.
    If extraction fails for ANY video, falls back to sorted positional
    indices for ALL videos (to avoid mixing strategies).

    Raises:
        ValueError: If extracted camera IDs have duplicates.
    """
    paths = [Path(p) for p in sorted(video_paths, key=lambda p: str(p))]

    # Try extracting IDs from filenames
    extracted: list[str | None] = [
        extract_camera_id_from_filename(p) for p in paths
    ]

    if all(eid is not None for eid in extracted):
        ids = [eid for eid in extracted if eid is not None]  # appease type checker
        if len(set(ids)) != len(ids):
            raise ValueError(
                f"Duplicate camera IDs extracted from filenames: {ids}"
            )
        logger.info(f"Extracted camera IDs from filenames: {ids}")
        return {cam_id: path for cam_id, path in zip(ids, paths)}

    # Fallback: positional indices
    logger.warning(
        "Could not extract camera IDs from all video filenames. "
        "Falling back to positional indices. "
        f"Extraction results: {list(zip([p.name for p in paths], extracted))}"
    )
    return {str(i): path for i, path in enumerate(paths)}


class CameraGroupIdentity(BaseModel):
    """Maps camera IDs to their calibrated camera models.

    Ensures a consistent, explicit mapping between the camera IDs used
    in a recording session and the camera parameters from calibration.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    camera_ids: list[str]

    @model_validator(mode="after")
    def _validate_unique(self) -> "CameraGroupIdentity":
        if len(set(self.camera_ids)) != len(self.camera_ids):
            raise ValueError(
                f"Camera IDs must be unique, got: {self.camera_ids}"
            )
        if len(self.camera_ids) < 1:
            raise ValueError("Must have at least one camera ID")
        return self

    @property
    def n_cameras(self) -> int:
        return len(self.camera_ids)

    def index_of(self, camera_id: str) -> int:
        """Get the index of a camera ID. Raises ValueError if not found."""
        try:
            return self.camera_ids.index(camera_id)
        except ValueError:
            raise ValueError(
                f"Camera '{camera_id}' not in group. Known: {self.camera_ids}"
            )

    def validate_against_calibration_names(
        self,
        calibration_camera_names: list[str],
    ) -> None:
        """Verify all our camera IDs exist in the calibration.

        Raises:
            KeyError: If any camera ID is missing from the calibration.
        """
        cal_set = set(calibration_camera_names)
        missing = [cid for cid in self.camera_ids if cid not in cal_set]
        if missing:
            raise KeyError(
                f"Cameras {missing} not found in calibration. "
                f"Calibration has: {calibration_camera_names}"
            )

    @classmethod
    def from_video_paths(cls, video_paths: list[Path | str]) -> "CameraGroupIdentity":
        """Build a CameraGroupIdentity by extracting IDs from video filenames."""
        id_to_path = camera_ids_from_video_paths(video_paths=video_paths)
        return cls(camera_ids=list(id_to_path.keys()))
