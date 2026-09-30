"""Persist Forge gap-filling provenance, including legacy saved report schemas."""
import numpy as np
from typing import Literal
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict
from skellyforge.core.trajectories.gap_filling import (
    GapFillingReport as ForgeGapFillingReport,
    TRAJECTORY_SUPPORT_SECONDS,
    fill_trajectory_gaps as forge_fill_trajectory_gaps,
)




class GapFillingReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    # Accept saved reports from before endpoint extrapolation was removed.
    algorithm_version: Literal[2, 3, 4] = 4
    trajectory_support_seconds: float = TRAJECTORY_SUPPORT_SECONDS
    # (keypoint index, start frame index, exclusive stop); indices use the saved grid.
    filled_spans: tuple[tuple[int, int, int], ...] = ()
    discarded_spans: tuple[tuple[int, int, int], ...] = ()
    unsupported_keypoint_indices: tuple[int, ...] = ()
    method: Literal["timestamp_linear_interior_nearest_endpoint", "timestamp_linear_interior", "timestamp_linear_visible_intervals"] = "timestamp_linear_visible_intervals"
    active_spans: tuple[tuple[int, int], ...] = ()
    blank_spans: tuple[tuple[int, int], ...] = ()

    def measured_support(self, points: NDArray[np.float64]) -> NDArray[np.bool_]:
        return ForgeGapFillingReport(**self.model_dump()).measured_support(points)

    def original_support(self, points: NDArray[np.float64]) -> NDArray[np.bool_]:
        return ForgeGapFillingReport(**self.model_dump()).original_support(points)


def fill_trajectory_gaps(
    *, points: NDArray[np.float64], timestamps_s: NDArray[np.float64],
) -> tuple[NDArray[np.float64], GapFillingReport]:
    completed, report = forge_fill_trajectory_gaps(points=points, timestamps_s=timestamps_s)
    return completed, GapFillingReport.model_validate(report.to_dict())
