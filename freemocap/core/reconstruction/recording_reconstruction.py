"""Inputs and results at the recording-wide skeleton reconstruction boundary."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from skellyforge.core.skeleton.pose.model_scale_fitting import ModelScaleFit

from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle


@dataclass(frozen=True, slots=True)
class RecordingReconstructionInput:
    bundles: tuple[TrackedSkeletonBundle, ...]
    keypoint_names: tuple[str, ...]
    keypoints_3d: NDArray[np.float64]
    compute_center_of_mass: bool
    timing: PosthocTimingReport

    @property
    def frame_count(self) -> int:
        return self.keypoints_3d.shape[0]

    def __post_init__(self) -> None:
        if (
            self.keypoints_3d.ndim != 3
            or self.keypoints_3d.shape[1:] != (len(self.keypoint_names), 3)
            or self.frame_count < 1
        ):
            raise ValueError("Expected a nonempty (frames, keypoints, 3) recording")
        if np.isinf(self.keypoints_3d).any():
            raise ValueError("Reconstruction input cannot contain infinite coordinates")
        if len(set(self.keypoint_names)) != len(self.keypoint_names):
            raise ValueError("Keypoint names must be unique")
        if not self.bundles or len({bundle.model_id for bundle in self.bundles}) != len(
            self.bundles
        ):
            raise ValueError(
                "Recording reconstruction requires unique bundle model IDs"
            )


@dataclass(frozen=True, slots=True)
class ModelRecordingReconstruction:
    frames: tuple[SkeletonReconstruction | None, ...]
    scale_fit: ModelScaleFit | None
