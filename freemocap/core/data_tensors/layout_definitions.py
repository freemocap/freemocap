"""Declared array axes, source identities and prepared numerical selections.

These definitions describe layout only. They do not assign timestamps, copy
scientific payloads, impose coordinate dimensions or establish array ownership.
The same authored order applies to live and recorded consumers.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field, replace

import numpy as np
from numpy.typing import DTypeLike, NDArray


def _require_name(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")


@dataclass(frozen=True, slots=True)
class AxisDefinition:
    """An identified axis in authored order; numeric IDs are not array offsets."""

    axis_name: str
    identifiers: Iterable[str | int | np.integer]

    def __post_init__(self) -> None:
        _require_name(self.axis_name, "Axis name")
        if isinstance(self.identifiers, (str, bytes)):
            raise TypeError("Axis identifiers must be a sequence of individual IDs")
        identifiers = tuple(
            int(identifier) if isinstance(identifier, np.integer) else identifier
            for identifier in self.identifiers
        )
        if identifiers:
            identifier_type = type(identifiers[0])
            if identifier_type not in (str, int) or any(
                type(identifier) is not identifier_type for identifier in identifiers
            ):
                raise ValueError("Axis identifiers must be uniformly strings or integers")
            if identifier_type is str:
                for identifier in identifiers:
                    _require_name(identifier, "Axis identifier")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(f"Duplicate identifiers in axis {self.axis_name!r}")
        object.__setattr__(self, "identifiers", identifiers)


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """Producer identity with a model-scoped instance number, initially zero."""

    source_id: str
    instance_id: int = 0
    sensor_group: str | None = None
    camera_id: str | None = None
    model_id: str | None = None

    def __post_init__(self) -> None:
        _require_name(self.source_id, "Source ID")
        if type(self.instance_id) is not int or self.instance_id < 0:
            raise ValueError("Instance ID must be a nonnegative integer")
        for label, value in (
            ("Sensor group", self.sensor_group),
            ("Camera ID", self.camera_id),
            ("Model ID", self.model_id),
        ):
            if value is not None:
                _require_name(value, label)


@dataclass(frozen=True, slots=True)
class TensorLayout:
    """Complete ordered axes and numerical interpretation of a data tensor.

    ``component_units`` follows ``component_identity`` exactly when supplied.
    Reference identities name an externally declared coordinate convention;
    no convention is inferred from component names or array dimensions.
    """

    axes: tuple[AxisDefinition, ...]
    dtype: DTypeLike
    component_units: tuple[str, ...] = ()
    reference_id: str | None = None
    source_identity: SourceIdentity | None = None
    channel_kind: str | None = None

    def __post_init__(self) -> None:
        axes = tuple(self.axes)
        if any(not isinstance(axis, AxisDefinition) for axis in axes):
            raise TypeError("Tensor axes must be AxisDefinition objects")
        if len({axis.axis_name for axis in axes}) != len(axes):
            raise ValueError("Tensor axis names must be unique")
        dtype = np.dtype(self.dtype)
        if dtype.fields is not None or dtype.subdtype is not None or dtype.kind not in "biufc":
            raise ValueError("Tensor dtype must be a scalar boolean or numeric dtype")
        units = tuple(self.component_units)
        if units:
            component_axis = next(
                (axis for axis in axes if axis.axis_name == "component_identity"), None
            )
            if component_axis is None or len(units) != len(component_axis.identifiers):
                raise ValueError("Component units must match the component_identity axis")
            for unit in units:
                _require_name(unit, "Component unit")
        if self.reference_id is not None:
            _require_name(self.reference_id, "Reference ID")
        if self.channel_kind is not None:
            _require_name(self.channel_kind, "Channel kind")
        if self.source_identity is not None and not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("Source identity must be a SourceIdentity object")
        object.__setattr__(self, "axes", axes)
        object.__setattr__(self, "dtype", dtype)
        object.__setattr__(self, "component_units", units)

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(len(axis.identifiers) for axis in self.axes)

    def axis_index(self, axis_name: str) -> int:
        for index, axis in enumerate(self.axes):
            if axis.axis_name == axis_name:
                return index
        raise ValueError(f"Undeclared tensor axis {axis_name!r}")

    def validate_array(self, values: NDArray) -> None:
        """Check the boundary without copying, casting or repairing values."""
        if not isinstance(values, np.ndarray):
            raise TypeError("Tensor values must be a NumPy array")
        if values.shape != self.shape:
            raise ValueError(f"Tensor shape {values.shape} does not match declared shape {self.shape}")
        if values.dtype != self.dtype:
            raise ValueError(f"Tensor dtype {values.dtype} does not match declared dtype {self.dtype}")

    def prepare_selection(
        self, axis_name: str, identifiers: Iterable[str | int | np.integer]
    ) -> "AxisSelection":
        return AxisSelection(self, axis_name, identifiers)


@dataclass(frozen=True, slots=True)
class AxisSelection:
    """Prepared axis selection bound to the full source layout.

    Contiguous ascending selections return views. Other selections use one
    NumPy gather allocation. Output mutability/ownership is not changed here;
    published read-only payloads are the responsibility of their storage owner.
    """

    source_layout: TensorLayout
    axis_name: str
    identifiers: Iterable[str | int | np.integer]
    result_layout: TensorLayout = field(init=False)
    _axis_index: int = field(init=False, repr=False)
    _indices: NDArray = field(init=False, repr=False, compare=False)
    _slice_range: slice | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        selected_axis = AxisDefinition(self.axis_name, self.identifiers)
        axis_index = self.source_layout.axis_index(self.axis_name)
        source_axis = self.source_layout.axes[axis_index]
        positions = {identifier: index for index, identifier in enumerate(source_axis.identifiers)}
        try:
            indices = tuple(positions[identifier] for identifier in selected_axis.identifiers)
        except KeyError as error:
            raise ValueError(f"Undeclared identifier {error.args[0]!r} in axis {self.axis_name!r}") from None
        slice_range = None
        if not indices:
            slice_range = slice(0, 0)
        elif indices == tuple(range(indices[0], indices[0] + len(indices))):
            slice_range = slice(indices[0], indices[0] + len(indices))
        result_axes = list(self.source_layout.axes)
        result_axes[axis_index] = selected_axis
        result_units = self.source_layout.component_units
        if self.axis_name == "component_identity" and result_units:
            result_units = tuple(result_units[index] for index in indices)
        object.__setattr__(self, "identifiers", selected_axis.identifiers)
        object.__setattr__(self, "_axis_index", axis_index)
        # Immutable backing bytes prevent accidental mutation of a prepared plan.
        object.__setattr__(self, "_indices", np.frombuffer(np.asarray(indices, dtype=np.intp).tobytes(), dtype=np.intp))
        object.__setattr__(self, "_slice_range", slice_range)
        object.__setattr__(self, "result_layout", replace(self.source_layout, axes=tuple(result_axes), component_units=result_units))

    @property
    def shares_memory(self) -> bool:
        """Whether selection uses a slice rather than a numerical gather."""
        return self._slice_range is not None

    def select_values(self, values: NDArray, *, source_layout: TensorLayout) -> NDArray:
        if source_layout != self.source_layout:
            raise ValueError("Selection source layout does not match its prepared layout")
        source_layout.validate_array(values)
        if self._slice_range is not None:
            slices = [slice(None)] * values.ndim
            slices[self._axis_index] = self._slice_range
            return values[tuple(slices)]
        return np.take(values, self._indices, axis=self._axis_index)
