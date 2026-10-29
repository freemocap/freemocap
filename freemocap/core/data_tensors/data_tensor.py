"""Numerical payloads and explicitly aligned scientific metadata.

Admission borrows arrays explicitly. Published copies use immutable numerical
backing, and safe views require published input. Frozen attributes alone do not
make borrowed arrays immutable.
"""

from dataclasses import dataclass, field, replace
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from freemocap.core.data_tensors.layout_definitions import AxisDefinition, AxisSelection, TensorLayout


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")


def _immutable_values(values: NDArray) -> NDArray:
    """Copy into immutable backing; writeability cannot be re-enabled."""
    return np.frombuffer(values.tobytes(order="C"), dtype=values.dtype).reshape(values.shape)


def _trusted_axis(axis: AxisDefinition, selection: slice) -> AxisDefinition:
    result = object.__new__(AxisDefinition)
    object.__setattr__(result, "axis_name", axis.axis_name)
    object.__setattr__(result, "identifiers", axis.identifiers[selection])
    return result


def _trusted_companion(companion: "CompanionTensor", values: NDArray, layout: TensorLayout) -> "CompanionTensor":
    result = object.__new__(CompanionTensor)
    object.__setattr__(result, "metadata_name", companion.metadata_name)
    object.__setattr__(result, "data_values", values)
    object.__setattr__(result, "tensor_layout", layout)
    return result


@dataclass(frozen=True, slots=True)
class ScientificProvenance:
    """Meaning and derivation, independent of numerical storage organization."""

    meaning: str
    operation_id: str
    input_refs: tuple[str, ...] = ()
    model_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.meaning, "Scientific meaning")
        _require_text(self.operation_id, "Producing operation")
        references = tuple(self.input_refs)
        for reference in references:
            _require_text(reference, "Input reference")
        if self.model_id is not None:
            _require_text(self.model_id, "Model identity")
        object.__setattr__(self, "input_refs", references)


@dataclass(frozen=True, slots=True, eq=False)
class CompanionTensor:
    """A named typed payload associated with declared axes of another tensor."""

    metadata_name: str
    data_values: NDArray
    tensor_layout: TensorLayout

    def __post_init__(self) -> None:
        _require_text(self.metadata_name, "Companion metadata name")
        self.tensor_layout.validate_array(self.data_values)
        kind = self.data_values.dtype.kind
        if self.metadata_name in ("entry_presence", "value_validity", "measured_support") and kind != "b":
            raise ValueError(f"{self.metadata_name} requires boolean values")
        if self.metadata_name == "confidence_scores" and kind != "f":
            raise ValueError("confidence_scores requires floating values")
        if self.metadata_name == "solver_status" and kind not in "iu":
            raise ValueError("solver_status requires integer values")

    def validate_parent(self, parent_layout: TensorLayout) -> None:
        """Match axis identities, not merely lengths that happen to broadcast."""
        parent_positions = {axis.axis_name: index for index, axis in enumerate(parent_layout.axes)}
        positions = []
        for axis in self.tensor_layout.axes:
            if axis.axis_name not in parent_positions:
                raise ValueError(f"Companion axis {axis.axis_name!r} is not declared by the parent")
            position = parent_positions[axis.axis_name]
            if axis != parent_layout.axes[position]:
                raise ValueError(f"Companion axis {axis.axis_name!r} has different identifiers or ordering")
            positions.append(position)
        if positions != sorted(positions):
            raise ValueError("Companion axes must follow parent axis ordering")
        if self.metadata_name in ("entry_presence", "value_validity") and self.tensor_layout.axes != parent_layout.axes:
            raise ValueError(f"{self.metadata_name} requires all parent axes")
        if (self.tensor_layout.source_identity is not None
                and self.tensor_layout.source_identity != parent_layout.source_identity):
            raise ValueError("Companion source identity differs from its parent")

    def aligned_values(self, parent_layout: TensorLayout) -> NDArray:
        """Expose a broadcast view using declared axis associations, without copying."""
        self.validate_parent(parent_layout)
        dimensions = {axis.axis_name: len(axis.identifiers) for axis in self.tensor_layout.axes}
        shape = tuple(dimensions.get(axis.axis_name, 1) for axis in parent_layout.axes)
        return np.broadcast_to(self.data_values.reshape(shape), parent_layout.shape)


@dataclass(frozen=True, slots=True, eq=False)
class DataTensor:
    """A numerical tensor with explicit ownership, provenance and aligned metadata."""

    data_values: NDArray
    tensor_layout: TensorLayout
    scientific_provenance: ScientificProvenance
    companion_tensors: tuple[CompanionTensor, ...] = ()
    storage_mode: Literal["borrowed", "mutable", "immutable"] = field(default="borrowed", init=False)

    def __post_init__(self) -> None:
        self.tensor_layout.validate_array(self.data_values)
        if not isinstance(self.scientific_provenance, ScientificProvenance):
            raise TypeError("Scientific provenance must be explicitly declared")
        companions = tuple(self.companion_tensors)
        if len({item.metadata_name for item in companions}) != len(companions):
            raise ValueError("Companion metadata names must be unique")
        for companion in companions:
            companion.validate_parent(self.tensor_layout)
        by_name = {item.metadata_name: item for item in companions}
        validity = by_name.get("value_validity")
        if validity is not None:
            present = by_name.get("entry_presence")
            if present is not None and np.any(validity.data_values & ~present.data_values):
                raise ValueError("Valid values must have entry presence")
            if np.any(validity.data_values & ~np.isfinite(self.data_values)):
                raise ValueError("Valid values must be finite")
        object.__setattr__(self, "companion_tensors", companions)

    def companion_values(self, metadata_name: str) -> NDArray:
        """Return the declared metadata payload without inventing missing fields."""
        for companion in self.companion_tensors:
            if companion.metadata_name == metadata_name:
                return companion.data_values
        raise KeyError(metadata_name)

    @property
    def is_immutable(self) -> bool:
        return self.storage_mode == "immutable"

    def immutable_copy(self) -> "DataTensor":
        """Publish an independent immutable payload, or reuse a published one.

        Borrowed buffers, including memory maps, must still be alive here. Every
        companion is copied too; changing an input alias cannot change the result.
        """
        if self.is_immutable:
            return self
        companions = tuple(CompanionTensor(item.metadata_name, _immutable_values(item.data_values), item.tensor_layout)
                           for item in self.companion_tensors)
        result = DataTensor(_immutable_values(self.data_values), self.tensor_layout,
                            self.scientific_provenance, companions)
        object.__setattr__(result, "storage_mode", "immutable")
        return result

    def mutable_copy(self) -> "DataTensor":
        """Return owned writable values and metadata, independent of the source."""
        companions = tuple(CompanionTensor(item.metadata_name, np.array(item.data_values, copy=True), item.tensor_layout)
                           for item in self.companion_tensors)
        result = DataTensor(np.array(self.data_values, copy=True), self.tensor_layout,
                            self.scientific_provenance, companions)
        object.__setattr__(result, "storage_mode", "mutable")
        return result

    def _require_immutable(self) -> None:
        if not self.is_immutable:
            raise ValueError("Safe tensor selections require immutable_copy() first")

    def _selected_tensor(self, values: NDArray, layout: TensorLayout,
                         companions: tuple[CompanionTensor, ...]) -> "DataTensor":
        """Internal selection of validated immutable input; no payload rescan."""
        result = object.__new__(DataTensor)
        object.__setattr__(result, "data_values", values)
        object.__setattr__(result, "tensor_layout", layout)
        object.__setattr__(result, "scientific_provenance", self.scientific_provenance)
        object.__setattr__(result, "companion_tensors", companions)
        object.__setattr__(result, "storage_mode", "immutable")
        return result

    def slice_axis(self, axis_name: str, start: int = 0, stop: int | None = None) -> "DataTensor":
        """Select positional bounds with shared numerical backing and no rescans."""
        self._require_immutable()
        if type(start) is not int or (stop is not None and type(stop) is not int):
            raise TypeError("Tensor slice bounds must be integers")
        axis_index = self.tensor_layout.axis_index(axis_name)
        selection = slice(start, stop)
        selected_axis = _trusted_axis(self.tensor_layout.axes[axis_index], selection)

        def selected_layout(layout: TensorLayout) -> TensorLayout:
            axes = tuple(selected_axis if axis.axis_name == axis_name else axis for axis in layout.axes)
            units = layout.component_units
            if axis_name == "component_identity" and units:
                units = units[selection]
            return replace(layout, axes=axes, component_units=units)

        slices = [slice(None)] * self.data_values.ndim
        slices[axis_index] = selection
        companions = []
        for item in self.companion_tensors:
            if not any(axis.axis_name == axis_name for axis in item.tensor_layout.axes):
                companions.append(item)
                continue
            companion_slices = [slice(None)] * item.data_values.ndim
            companion_slices[item.tensor_layout.axis_index(axis_name)] = selection
            companions.append(_trusted_companion(item, item.data_values[tuple(companion_slices)], selected_layout(item.tensor_layout)))
        return self._selected_tensor(self.data_values[tuple(slices)], selected_layout(self.tensor_layout), tuple(companions))

    def select_axis(self, selection: AxisSelection) -> "DataTensor":
        """Use a prepared selection; gathers allocate and freeze bounded outputs.

        A noncontiguous gather needs a numerical output plus its immutable backing
        copy. Contiguous selections share existing values and companion storage.
        """
        self._require_immutable()
        values = selection.select_values(self.data_values, source_layout=self.tensor_layout)
        if not selection.shares_memory:
            values = _immutable_values(values)
        companions = []
        for item in self.companion_tensors:
            if not any(axis.axis_name == selection.axis_name for axis in item.tensor_layout.axes):
                companions.append(item)
                continue
            companion_selection = item.tensor_layout.prepare_selection(selection.axis_name, selection.identifiers)
            selected_values = companion_selection.select_values(item.data_values, source_layout=item.tensor_layout)
            if not companion_selection.shares_memory:
                selected_values = _immutable_values(selected_values)
            companions.append(_trusted_companion(item, selected_values, companion_selection.result_layout))
        return self._selected_tensor(values, selection.result_layout, tuple(companions))
