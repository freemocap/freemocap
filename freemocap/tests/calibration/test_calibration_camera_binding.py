"""Binding live cameras to a loaded calibration is total, injective, or refused."""

import logging

import numpy as np
import pytest

from freemocap.core.tasks.calibration.shared.calibration_camera_binding import (
    CalibrationMatchKind,
    bind_calibration_to_live_cameras,
)
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


def build_calibration_camera(camera_id: str, index: int) -> CameraModel:
    return CameraModel(
        id=camera_id,
        index=index,
        image_size=(1280, 720),
        intrinsics=CameraIntrinsics(fx=900.0, fy=900.0, cx=640.0, cy=360.0),
        extrinsics=CameraExtrinsics(
            quaternion_wxyz=np.array([1.0, 0.0, 0.0, 0.0]),
            translation=np.array([float(index) * 100.0, 0.0, 0.0]),
        ),
    )


def test_reported_double_bind_is_refused() -> None:
    """The regression case from the log storm.

    Live `583d` matched the calibration exactly, yet calibration `583d` was ALSO
    index-bound onto live `be07` — one calibration entry serving two cameras, and three
    cameras handed another camera's intrinsics. The id sets overlap, so the index order
    is not a relabelling of the same rig and the whole pass must be refused.
    """
    binding = bind_calibration_to_live_cameras(
        calibration_cameras=[
            build_calibration_camera("099c", 0),
            build_calibration_camera("fa5a", 1),
            build_calibration_camera("583d", 2),
        ],
        live_camera_indices={"d441": 0, "2ea4": 1, "be07": 2, "583d": 3},
    )

    assert binding.kind is CalibrationMatchKind.UNMATCHED
    assert binding.applicable is False
    assert set(binding.by_live_id) == {"d441", "2ea4", "be07", "583d"}
    assert all(model is None for model in binding.by_live_id.values())
    assert "583d" in binding.reason


def test_exact_id_match_binds_every_camera() -> None:
    calibration = [build_calibration_camera(f"cam{i}", i) for i in range(3)]

    binding = bind_calibration_to_live_cameras(
        calibration_cameras=calibration,
        live_camera_indices={"cam0": 0, "cam1": 1, "cam2": 2},
    )

    assert binding.kind is CalibrationMatchKind.EXACT
    assert binding.applicable is True
    assert {live_id: model.id for live_id, model in binding.by_live_id.items()} == {
        "cam0": "cam0",
        "cam1": "cam1",
        "cam2": "cam2",
    }


def test_live_subset_of_calibration_matches_exactly() -> None:
    """A camera being unplugged leaves its calibration entry unused, not the rig broken."""
    binding = bind_calibration_to_live_cameras(
        calibration_cameras=[build_calibration_camera(f"cam{i}", i) for i in range(3)],
        live_camera_indices={"cam0": 0, "cam2": 2},
    )

    assert binding.kind is CalibrationMatchKind.EXACT
    assert binding.applicable is True
    assert set(binding.by_live_id) == {"cam0", "cam2"}


def test_disjoint_ids_bind_by_structured_index() -> None:
    """Ids drifted but the rig is the same size and the id spaces do not overlap."""
    binding = bind_calibration_to_live_cameras(
        calibration_cameras=[
            build_calibration_camera("099c", 0),
            build_calibration_camera("fa5a", 1),
            build_calibration_camera("7b21", 2),
        ],
        live_camera_indices={"d441": 0, "2ea4": 1, "be07": 2},
    )

    assert binding.kind is CalibrationMatchKind.INDEX
    assert binding.applicable is True
    assert {live_id: model.id for live_id, model in binding.by_live_id.items()} == {
        "d441": "099c",
        "2ea4": "fa5a",
        "be07": "7b21",
    }
    assert binding.live_id_for_calibration_id == {"099c": "d441", "fa5a": "2ea4", "7b21": "be07"}


def test_two_live_cameras_sharing_an_index_is_refused() -> None:
    """Non-injective: both live cameras would claim the same calibration camera."""
    binding = bind_calibration_to_live_cameras(
        calibration_cameras=[
            build_calibration_camera("099c", 0),
            build_calibration_camera("fa5a", 1),
        ],
        live_camera_indices={"d441": 0, "2ea4": 0},
    )

    assert binding.kind is CalibrationMatchKind.UNMATCHED
    assert binding.applicable is False


def test_live_index_absent_from_calibration_is_refused() -> None:
    """Not total: a partial binding is not a binding."""
    binding = bind_calibration_to_live_cameras(
        calibration_cameras=[
            build_calibration_camera("099c", 0),
            build_calibration_camera("fa5a", 1),
        ],
        live_camera_indices={"d441": 0, "2ea4": 1, "be07": 2},
    )

    assert binding.kind is CalibrationMatchKind.UNMATCHED
    assert binding.applicable is False
    assert all(model is None for model in binding.by_live_id.values())


def test_calibration_reusing_an_index_is_refused() -> None:
    binding = bind_calibration_to_live_cameras(
        calibration_cameras=[
            build_calibration_camera("099c", 0),
            build_calibration_camera("fa5a", 0),
        ],
        live_camera_indices={"d441": 0, "2ea4": 1},
    )

    assert binding.kind is CalibrationMatchKind.UNMATCHED
    assert binding.applicable is False


@pytest.mark.parametrize(
    "calibration_cameras, live_camera_indices",
    [
        ([], {"d441": 0}),
        ([build_calibration_camera("099c", 0)], {}),
    ],
)
def test_empty_sides_are_unmatched_not_crashes(calibration_cameras, live_camera_indices) -> None:
    binding = bind_calibration_to_live_cameras(
        calibration_cameras=calibration_cameras,
        live_camera_indices=live_camera_indices,
    )

    assert binding.applicable is False
    assert binding.kind is CalibrationMatchKind.UNMATCHED


def test_binding_is_pure(caplog: pytest.LogCaptureFixture) -> None:
    """No logging, and the same input always yields the same answer.

    Purity is what lets the caller warn exactly once instead of every frame.
    """
    calibration = [build_calibration_camera("099c", 0), build_calibration_camera("fa5a", 1)]
    live = {"d441": 0, "2ea4": 5}

    with caplog.at_level(logging.DEBUG):
        first = bind_calibration_to_live_cameras(
            calibration_cameras=calibration, live_camera_indices=live
        )
        second = bind_calibration_to_live_cameras(
            calibration_cameras=calibration, live_camera_indices=live
        )

    assert caplog.records == []
    assert first == second
