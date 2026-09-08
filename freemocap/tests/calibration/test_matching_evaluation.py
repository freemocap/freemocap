"""Initial-binding checks and permutation recovery on held-out observations."""

from dataclasses import replace

import numpy as np

from freemocap.core.tasks.calibration.camera_matching.matching_evaluation import match_camera_geometry
from freemocap.core.tasks.calibration.camera_matching.matching_models import (
    CameraMatchingConfig,
    CameraMatchingRequest,
    CameraMatchingStatus,
)
from freemocap.tests.calibration.test_matching_fitness import camera_rig, observations


def matching_request() -> CameraMatchingRequest:
    cameras = camera_rig()
    return CameraMatchingRequest(
        source_ids=("arbitrary renamed.mov", "another video.mp4", "a.3.avi"),
        image_sizes=tuple(camera.image_size for camera in cameras),
        cameras=cameras, pixels=observations(cameras), initial_assignment=(0, 1, 2), config=CameraMatchingConfig(),
    )


def test_healthy_initial_binding_does_not_search() -> None:
    result = match_camera_geometry(request=matching_request())
    assert result.status is CameraMatchingStatus.INITIAL_ACCEPTED
    assert result.search is None


def test_renamed_permuted_sources_recover_fixed_geometry() -> None:
    request = matching_request()
    result = match_camera_geometry(request=replace(request, pixels=request.pixels[[2, 0, 1]]))
    assert result.status is CameraMatchingStatus.MATCHED
    assert result.assignment == (2, 0, 1)
    assert result.search is not None and result.search.complete


def test_missing_tracks_preserve_initial_attempt_without_search() -> None:
    request = matching_request()
    result = match_camera_geometry(request=replace(request, pixels=np.full_like(request.pixels, np.nan)))
    assert result.status is CameraMatchingStatus.INSUFFICIENT
    assert result.assignment == request.initial_assignment
    assert result.search is None


def test_disabling_search_preserves_available_binding() -> None:
    request = matching_request()
    result = match_camera_geometry(request=replace(request, config=CameraMatchingConfig(automatically_match=False)))
    assert result.status is CameraMatchingStatus.DISABLED
    assert result.assignment == request.initial_assignment
    assert result.search is None


def test_validation_rejects_search_winner_with_inconsistent_later_frames() -> None:
    request = matching_request()
    pixels = request.pixels[[2, 0, 1]].copy()
    pixels[:, 1::2] = request.pixels[:, 1::2]
    result = match_camera_geometry(request=replace(request, pixels=pixels))
    assert result.status in (CameraMatchingStatus.POOR, CameraMatchingStatus.AMBIGUOUS)
    assert result.search is not None


def test_search_limit_retains_best_effort_candidate_without_certifying_it() -> None:
    request = matching_request()
    result = match_camera_geometry(request=replace(
        request, initial_assignment=None, config=CameraMatchingConfig(maximum_search_nodes=4),
    ))
    assert result.status is CameraMatchingStatus.SEARCH_LIMIT
    assert result.assignment is not None
    assert result.search is not None and not result.search.complete
