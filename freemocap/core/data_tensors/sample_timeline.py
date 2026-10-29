"""Bind existing sample identifiers and timestamps without generating timing."""

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from freemocap.core.data_tensors.layout_definitions import AxisDefinition, SourceIdentity


@dataclass(frozen=True, slots=True, eq=False, kw_only=True)
class SampleTimeline:
    """An immutable selection of samples within one identified clock epoch.

    Inputs are validated and copied at admission. Numerical slices share the
    immutable backing buffers and preserve original IDs and timestamps. Clock
    identity is supplied by the caller; this class does not establish clock
    relationships, estimate timestamps or synchronize sources.
    """

    timeline_id: str
    clock_id: str
    source_identity: SourceIdentity
    sample_ids: Sequence[int] | NDArray
    timestamps_s: Sequence[float] | NDArray
    clock_epoch: int = 0
    _sample_axis: AxisDefinition | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        for field_name, value in (("Timeline ID", self.timeline_id), ("Clock ID", self.clock_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a nonempty string")
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("Timeline source must be a SourceIdentity")
        if type(self.clock_epoch) is not int or self.clock_epoch < 0:
            raise ValueError("Clock epoch must be a nonnegative integer")

        identifiers = np.asarray(self.sample_ids)
        timestamps = np.asarray(self.timestamps_s)
        if identifiers.ndim != 1 or timestamps.ndim != 1:
            raise ValueError("Sample identifiers and timestamps must be one-dimensional")
        if identifiers.size != timestamps.size:
            raise ValueError("Sample identifiers and timestamps must have equal lengths")
        if identifiers.size:
            if identifiers.dtype.kind not in "iu":
                raise ValueError("Sample identifiers must be integers")
            if np.any(identifiers < 0) or np.any(identifiers > np.iinfo(np.int64).max):
                raise ValueError("Sample identifiers must fit nonnegative int64")
        if timestamps.size and timestamps.dtype.kind not in "iuf":
            raise ValueError("Sample timestamps must be real numbers")

        identifiers = np.asarray(identifiers, dtype=np.int64)
        timestamps = np.asarray(timestamps, dtype=np.float64)
        if identifiers.size > 1 and np.any(identifiers[1:] <= identifiers[:-1]):
            raise ValueError("Sample identifiers must strictly increase; gaps are allowed")
        if not np.isfinite(timestamps).all() or (
            timestamps.size > 1 and np.any(timestamps[1:] <= timestamps[:-1])
        ):
            raise ValueError("Sample timestamps must be finite and strictly increase")

        # Immutable bytes prevent re-enabling array writes through published views.
        object.__setattr__(self, "sample_ids", np.frombuffer(identifiers.tobytes(), dtype=np.int64))
        object.__setattr__(self, "timestamps_s", np.frombuffer(timestamps.tobytes(), dtype=np.float64))

    @property
    def sample_count(self) -> int:
        return len(self.sample_ids)

    @property
    def sample_axis(self) -> AxisDefinition:
        """Build identifier metadata once, then share it across channel layouts."""
        sample_axis = self._sample_axis
        if sample_axis is None:
            sample_axis = AxisDefinition("sample_identity", self.sample_ids)
            object.__setattr__(self, "_sample_axis", sample_axis)
        return sample_axis

    def slice_samples(self, start: int = 0, stop: int | None = None) -> "SampleTimeline":
        """Select by array position, retaining sample identity and clock meaning.

        Uses Python slice bounds (including negative bounds). Empty selections
        are valid. No timing calculation, numerical copy or revalidation occurs.
        """
        if type(start) is not int or (stop is not None and type(stop) is not int):
            raise TypeError("Sample slice bounds must be integers")
        selection = slice(start, stop)
        result = object.__new__(type(self))
        for field_name in ("timeline_id", "clock_id", "source_identity", "clock_epoch"):
            object.__setattr__(result, field_name, getattr(self, field_name))
        object.__setattr__(result, "sample_ids", self.sample_ids[selection])
        object.__setattr__(result, "timestamps_s", self.timestamps_s[selection])
        sample_axis = None
        if self._sample_axis is not None:
            # Source metadata is already validated. Preserve it without rescanning IDs.
            sample_axis = object.__new__(AxisDefinition)
            object.__setattr__(sample_axis, "axis_name", self._sample_axis.axis_name)
            object.__setattr__(sample_axis, "identifiers", self._sample_axis.identifiers[selection])
        object.__setattr__(result, "_sample_axis", sample_axis)
        return result
