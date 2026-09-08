"""Live matching installs one binding through an owned background worker."""

import time
from pathlib import Path

from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.tasks.calibration.camera_matching.live_matching import LiveGeometryMatcher
from freemocap.core.tasks.calibration.shared.calibration_camera_binding import CalibrationMatchKind
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.tests.calibration.test_posthoc_matching import recorded_request


def test_background_matching_installs_source_binding_and_closes(tmp_path: Path) -> None:
    request = recorded_request()
    path = tmp_path / "calibration.toml"
    CalibrationResult(
        cameras=list(request.cameras), board=CharucoBoardDefinition.create_letter_size_5x3(),
        reprojection_error_px=0.0, initial_cost=0.0, final_cost=0.0, n_iterations=0,
        time_seconds=0.0, n_observations_used=120, n_observations_rejected=0,
    ).dump_anipose_toml(path=path)
    calibration = CalibrationStateTracker.create_and_try_load(calibration_toml_path=path)
    matcher = LiveGeometryMatcher(calibration=calibration, camera_indices={source: index for index, source in enumerate(request.videos)})
    try:
        for index in range(24):
            matcher.update(observations=request.frames[index % len(request.frames)], config=request.config, elapsed_seconds=float(index))
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            matcher.update(observations={}, config=request.config, elapsed_seconds=24.0)
            if calibration.binding is not None and calibration.binding.kind is CalibrationMatchKind.GEOMETRY:
                break
            time.sleep(0.01)
        assert calibration.is_applicable()
        assert calibration.binding is not None and calibration.binding.kind is CalibrationMatchKind.GEOMETRY
        assert tuple(camera.id for camera in calibration.binding.by_live_id.values()) == ("camera 2", "camera 0", "camera 1")
    finally:
        matcher.close()
