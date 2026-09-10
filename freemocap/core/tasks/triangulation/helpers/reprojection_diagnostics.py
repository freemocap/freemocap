"""Camera-by-point diagnostics in the triangulator's input coordinate units."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class ReprojectionSummary:
    observed_count: int
    reconstructed_count: int
    contributing_count: int
    mean_error: float | None
    rms_error: float | None
    maximum_error: float | None


@dataclass(frozen=True, slots=True)
class ReprojectionDiagnostics:
    """Axes are camera, optional frame, point; arrays precede downstream point gates."""

    errors: NDArray[np.float64]
    observed: NDArray[np.bool_]
    reconstructed: NDArray[np.bool_]
    weights: NDArray[np.float64]
    units: Literal['pixels', 'normalized']

    def __post_init__(self) -> None:
        if self.errors.ndim not in (2, 3) or any(array.shape != self.errors.shape for array in (self.observed, self.reconstructed, self.weights)):
            raise ValueError('Diagnostics require aligned camera, frame, point axes')

    def summaries(self) -> tuple[ReprojectionSummary, ...]:
        summaries: list[ReprojectionSummary] = []
        for index in range(self.errors.shape[0]):
            valid = self.observed[index] & self.reconstructed[index] & np.isfinite(self.errors[index])
            values = self.errors[index][valid]
            summaries.append(ReprojectionSummary(
                observed_count=int(self.observed[index].sum()), reconstructed_count=int(valid.sum()),
                contributing_count=int((valid & (self.weights[index] > 0.0)).sum()),
                mean_error=float(values.mean()) if values.size else None,
                rms_error=float(np.sqrt(np.mean(values ** 2))) if values.size else None,
                maximum_error=float(values.max()) if values.size else None,
            ))
        return tuple(summaries)


@dataclass(frozen=True, slots=True)
class NamedReprojectionDiagnostics:
    source_ids: tuple[str, ...]
    point_names: tuple[str, ...]
    values: ReprojectionDiagnostics

    def __post_init__(self) -> None:
        if len(self.source_ids) != self.values.errors.shape[0] or len(self.point_names) != self.values.errors.shape[-1]:
            raise ValueError('Diagnostic names must match numeric axes')
