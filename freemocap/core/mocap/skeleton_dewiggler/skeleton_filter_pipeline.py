"""
Skeleton filtering pipeline: One Euro Filter → Tree FABRIK.

Pipeline (per frame):
    1. Per-keypoint One Euro filtering (removes high-frequency jitter)
    2. Tree FABRIK solving (enforces bone length constraints, handles Y-splits)

Keypoints not in any FABRIK tree are returned filter-only (e.g. face landmarks,
torso anchors, head keypoints).

Usage:
    from skeleton_config import SkeletonDefinition
    from skeleton_filter_pipeline import FilterConfig, SkeletonFilterPipeline

    skeleton = SkeletonDefinition.mediapipe_body()
    config = FilterConfig(min_cutoff=0.004, beta=0.7)

    # From calibration frames:
    pipeline = SkeletonFilterPipeline.from_calibration(
        skeleton=skeleton,
        config=config,
        calibration_frames=my_cal_frames,
    )

    # Or with pre-computed bone lengths:
    pipeline = SkeletonFilterPipeline.from_bone_lengths(
        skeleton=skeleton,
        config=config,
        bone_lengths=my_bone_lengths,
    )

    for t, raw_positions in stream:
        clean = pipeline.process_frame(t=t, positions=raw_positions)
"""

from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel, ConfigDict

from fabrik_solver import FabrikTree, estimate_bone_lengths, solve_tree
from one_euro_filter import OneEuroFilter3D
from mediapipe_skeleton_config import SkeletonDefinition


class FilterConfig(BaseModel):
    """Tunable parameters for the filtering pipeline."""

    model_config = ConfigDict(frozen=True)

    # One Euro Filter params
    min_cutoff: float = 0.004
    beta: float = 0.7
    d_cutoff: float = 1.0

    # FABRIK params
    fabrik_tolerance: float = 1e-4
    fabrik_max_iterations: int = 20


@dataclass
class SkeletonFilterPipeline:
    """
    Frame-by-frame skeleton filtering pipeline.

    Step 1: One Euro filter on every keypoint (jitter removal).
    Step 2: Tree FABRIK on the skeleton's bone tree (bone length
            enforcement, including Y-splits like ankle→heel+foot_index
            or wrist→5 fingers).

    Keypoints not belonging to any FABRIK tree (face landmarks, torso
    anchors, head keypoints) are returned filter-only.
    """

    skeleton: SkeletonDefinition
    config: FilterConfig
    bone_lengths: dict[str, float]
    fabrik_tree: FabrikTree = field(repr=False)
    _filters: dict[str, OneEuroFilter3D] = field(
        default_factory=dict, init=False, repr=False,
    )
    _initialized: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        for bone in self.skeleton.bones:
            if bone.key not in self.bone_lengths:
                raise ValueError(f"Missing bone length for '{bone.key}'")
            if self.bone_lengths[bone.key] <= 0.0:
                raise ValueError(
                    f"Bone length must be positive for '{bone.key}', "
                    f"got {self.bone_lengths[bone.key]}"
                )

    @classmethod
    def from_calibration(
        cls,
        *,
        skeleton: SkeletonDefinition,
        config: FilterConfig,
        calibration_frames: list[dict[str, np.ndarray]],
    ) -> "SkeletonFilterPipeline":
        """
        Create pipeline from skeleton + calibration data.

        Bone lengths are estimated as median across calibration frames.
        """
        bone_lengths = estimate_bone_lengths(
            frames=calibration_frames,
            skeleton=skeleton,
        )
        fabrik_tree = FabrikTree.from_skeleton(
            skeleton=skeleton,
            bone_lengths=bone_lengths,
        )
        return cls(
            skeleton=skeleton,
            config=config,
            bone_lengths=bone_lengths,
            fabrik_tree=fabrik_tree,
        )

    @classmethod
    def from_bone_lengths(
        cls,
        *,
        skeleton: SkeletonDefinition,
        config: FilterConfig,
        bone_lengths: dict[str, float],
    ) -> "SkeletonFilterPipeline":
        """Create pipeline with pre-computed bone lengths."""
        fabrik_tree = FabrikTree.from_skeleton(
            skeleton=skeleton,
            bone_lengths=bone_lengths,
        )
        return cls(
            skeleton=skeleton,
            config=config,
            bone_lengths=bone_lengths,
            fabrik_tree=fabrik_tree,
        )

    def _initialize_filters(self, *, t: float, positions: dict[str, np.ndarray]) -> None:
        for name, pos in positions.items():
            self._filters[name] = OneEuroFilter3D(
                t0=t,
                x0=np.asarray(pos, dtype=np.float64),
                min_cutoff=self.config.min_cutoff,
                beta=self.config.beta,
                d_cutoff=self.config.d_cutoff,
            )
        self._initialized = True

    def process_frame(
        self,
        *,
        t: float,
        positions: dict[str, np.ndarray],
    ) -> dict[str, np.ndarray]:
        """
        Process one frame of raw keypoint positions.

        Args:
            t: timestamp in seconds (must be strictly increasing).
            positions: raw keypoint positions, mapping name → (3,) array.

        Returns:
            Filtered + bone-length-constrained positions.
        """
        if not self._initialized:
            self._initialize_filters(t=t, positions=positions)
            return {
                name: np.array(pos, dtype=np.float64)
                for name, pos in positions.items()
            }

        # --- Step 1: One Euro filter every keypoint ---
        filtered: dict[str, np.ndarray] = {}
        for name, pos in positions.items():
            if name not in self._filters:
                raise ValueError(
                    f"Keypoint '{name}' was not present in the first frame"
                )
            filtered[name] = self._filters[name](
                t=t,
                x=np.asarray(pos, dtype=np.float64),
            )

        # --- Step 2: Tree FABRIK ---
        if self.fabrik_tree.nodes:
            fabrik_targets: dict[str, np.ndarray] = {
                name: filtered[name]
                for name in self.fabrik_tree.topo_order
            }

            solved = solve_tree(
                targets=fabrik_targets,
                tree=self.fabrik_tree,
                tolerance=self.config.fabrik_tolerance,
                max_iterations=self.config.fabrik_max_iterations,
            )

            result: dict[str, np.ndarray] = {}
            for name, pos in filtered.items():
                if name in solved:
                    result[name] = solved[name]
                else:
                    result[name] = pos
        else:
            result = filtered

        return result