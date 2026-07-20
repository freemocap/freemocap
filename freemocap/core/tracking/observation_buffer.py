"""ObservationBuffer: lightweight replacement for skellytracker's BaseRecorder.

Collects per-frame Observation objects from the new skellytracker API and
provides array-conversion helpers used by triangulation and calibration tasks.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray  # noqa: TC002
from skellytracker.core.data_primitives.observation import Observation  # noqa: TC002


class ObservationBuffer:
    """Collects Observation objects and converts them to numpy arrays.

    Replaces the old skellytracker BaseRecorder which is no longer part of
    the public API.
    """

    def __init__(self) -> None:
        self.observations: list[Observation] = []

    def add_observation(self, observation: Observation) -> None:
        self.observations.append(observation)

    def to_keypoints_array(self) -> NDArray[np.float64]:
        """Return (frames, keypoints, 3) array by merging all stages per frame.

        Equivalent to the old BaseRecorder.to_array which called
        observation.to_2d_array() (which itself returned full xyz).
        """
        return np.stack([obs.to_keypoints().xyz for obs in self.observations]).astype(np.float64)

    def to_stage_array(self, stage_name: str, n_points: int | None = None) -> NDArray[np.float64]:
        """Return (frames, n_points, 3) array from a single named stage.

        Undetected points have visibility=0 in the source and NaN xy in the
        returned array. If n_points is given, only the first n_points keypoints
        are returned (useful for charuco, which prefixes charuco corners before
        aruco marker corners).

        Args:
            stage_name: Key in Observation.stages (e.g., "charuco", "body").
            n_points: If set, clamp output to the first n_points keypoints.
        """
        arrays: list[NDArray[np.float64]] = []
        for obs in self.observations:
            stage = obs.stages.get(stage_name)
            if stage is None or stage.keypoints is None:
                raise ValueError(
                    f"ObservationBuffer.to_stage_array: stage {stage_name!r} missing "
                    f"from observation at frame {obs.frame_number}"
                )
            kpts = stage.keypoints
            xyz = kpts.xyz if n_points is None else kpts.xyz[:n_points]
            vis = kpts.visibility if n_points is None else kpts.visibility[:n_points]
            xyz_out = xyz.copy().astype(np.float64)
            xyz_out[vis <= 0.0] = np.nan
            arrays.append(xyz_out)
        return np.stack(arrays)

    def clear(self) -> None:
        self.observations.clear()

    def __len__(self) -> int:
        return len(self.observations)
