"""Associate a tensor's sample axis with existing sample identifiers and times."""

from dataclasses import dataclass

from freemocap.core.data_tensors.data_tensor import DataTensor
from freemocap.core.data_tensors.sample_timeline import SampleTimeline


@dataclass(frozen=True, slots=True, eq=False)
class TimeSeries:
    """A tensor with one explicitly designated timeline; no resampling occurs."""

    data_tensor: DataTensor
    sample_timeline: SampleTimeline
    sample_axis_name: str = "sample_identity"

    def __post_init__(self) -> None:
        sample_axis = self.data_tensor.tensor_layout.axes[
            self.data_tensor.tensor_layout.axis_index(self.sample_axis_name)
        ]
        if sample_axis.identifiers != self.sample_timeline.sample_axis.identifiers:
            raise ValueError("Tensor sample identifiers must match the sample timeline exactly")

    @property
    def sample_count(self) -> int:
        return self.sample_timeline.sample_count

    @property
    def is_immutable(self) -> bool:
        return self.data_tensor.is_immutable

    def _with_tensor(self, data_tensor: DataTensor, sample_timeline: SampleTimeline) -> "TimeSeries":
        """Internal operation with already matched tensor/timeline sample axes."""
        result = object.__new__(TimeSeries)
        object.__setattr__(result, "data_tensor", data_tensor)
        object.__setattr__(result, "sample_timeline", sample_timeline)
        object.__setattr__(result, "sample_axis_name", self.sample_axis_name)
        return result

    def immutable_copy(self) -> "TimeSeries":
        if self.is_immutable:
            return self
        return self._with_tensor(self.data_tensor.immutable_copy(), self.sample_timeline)

    def mutable_copy(self) -> "TimeSeries":
        return self._with_tensor(self.data_tensor.mutable_copy(), self.sample_timeline)

    def slice_samples(self, start: int = 0, stop: int | None = None) -> "TimeSeries":
        """Slice values, companion tensors and original sample timing together."""
        tensor = self.data_tensor.slice_axis(self.sample_axis_name, start, stop)
        timeline = self.sample_timeline.slice_samples(start, stop)
        return self._with_tensor(tensor, timeline)

    def frame_view(self, index: int) -> "TimeSeries":
        """Return one sample as a view, retaining its length-one sample axis."""
        if type(index) is not int:
            raise TypeError("Frame index must be an integer")
        if index < 0:
            index += self.sample_count
        if index < 0 or index >= self.sample_count:
            raise IndexError("Frame index is outside the time series")
        return self.slice_samples(index, index + 1)
