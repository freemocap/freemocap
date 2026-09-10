"""Matching samples preserve named point identity and bound numeric memory."""

import numpy as np
import pytest
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.tasks.calibration.camera_matching.observation_sampling import (
    MatchingSampleLayout, MatchingSampleWindow, sample_recorded_observations,
)


def frame(number: int) -> dict[str, Observation]:
    return {
        source: Observation(frame_number=number, image_size=(480, 640), stages={
            "board": StageObservation(name="board", keypoints=Keypoints(
                names=names, xyz=np.array([[float(number), 20.0, 0.0], [30.0, 40.0, 0.0]]),
                visibility=np.array([1.0, 0.0]),
            )),
        })
        for source, names in (("left", ("a", "b")), ("right", ("b", "a")))
    }


def layout() -> MatchingSampleLayout:
    return MatchingSampleLayout(source_ids=("left", "right"), point_names=("board.a", "board.b"), image_sizes=((640, 480), (640, 480)), minimum_visibility=0.5)


def test_names_and_visibility_define_point_axis() -> None:
    pixels = layout().extract(observations=frame(3))
    assert pixels[0, 0, 0] == 3.0
    assert pixels[1, 1, 0] == 3.0
    assert np.isnan(pixels[0, 1]).all() and np.isnan(pixels[1, 0]).all()


def test_window_bounds_storage_and_copies_input() -> None:
    window = MatchingSampleWindow(layout=layout(), capacity=2, interval_seconds=0.2)
    for number in range(4):
        assert window.append(observations=frame(number), elapsed_seconds=float(number))
    snapshot = window.snapshot()
    assert snapshot.shape == (2, 2, 2, 2)
    assert snapshot[0, :, 0, 0].tolist() == [2.0, 3.0]
    snapshot[:] = 100.0
    assert window.snapshot()[0, 0, 0, 0] == 2.0
    assert not window.append(observations=frame(5), elapsed_seconds=3.1)


def test_posthoc_sampling_covers_recording_endpoints() -> None:
    pixels = sample_recorded_observations(layout=layout(), frames=[frame(i) for i in range(10)], maximum_frames=3)
    assert pixels[0, :, 0, 0].tolist() == [0.0, 4.0, 9.0]


def test_mismatched_frame_numbers_fail() -> None:
    observations = frame(0)
    observations["right"].frame_number = 1
    with pytest.raises(ValueError, match="synchronized"):
        layout().extract(observations=observations)
