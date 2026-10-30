"""Named access to a dense entity array, with prepared identity selections.

Mapping access is a convenience view; numerical consumers use ``data_values``,
``entry_present`` and ``aligned``. No numerical dictionary is retained. A live
frame's time identity belongs to its containing message, not its entity axis.
"""
from collections.abc import Mapping, Iterator
from functools import lru_cache

import numpy as np
from freemocap.core.data_tensors.layout_definitions import AxisDefinition, TensorLayout

SPATIAL_COMPONENTS = ("x", "y", "z")


@lru_cache(maxsize=256)
def _identity_columns(names: tuple[str, ...]) -> dict[str, int]:
    if len(set(names)) != len(names) or any(not isinstance(name, str) or not name for name in names):
        raise ValueError("Entity identities must be unique nonempty names")
    return {name: column for column, name in enumerate(names)}


@lru_cache(maxsize=512)
def _selection(source: tuple[str, ...], target: tuple[str, ...]) -> np.ndarray:
    columns = _identity_columns(source)
    _identity_columns(target)
    indices = np.asarray([columns.get(name, -1) for name in target], dtype=np.int64)
    indices.setflags(write=False)
    return indices


@lru_cache(maxsize=256)
def _channel_layout(names: tuple[str, ...], components: tuple[str, ...], dtype: str) -> TensorLayout:
    axes = (AxisDefinition("entity_identity", names),)
    if components:
        axes += (AxisDefinition("component_identity", components),)
    return TensorLayout(axes=axes, dtype=np.dtype(dtype))


class ChannelValues(Mapping):
    """Borrow dense values and an entity-presence mask; named reads return views."""

    def __init__(self, names: tuple[str, ...], data_values: np.ndarray, entry_present: np.ndarray | None = None, *, component_names: tuple[str, ...]) -> None:
        self.names = tuple(names)
        self._columns = _identity_columns(self.names)
        self.component_names = component_names
        self.data_values = np.asarray(data_values)
        self.tensor_layout = _channel_layout(self.names, component_names, self.data_values.dtype.str)
        self.tensor_layout.validate_array(self.data_values)
        if self.data_values.dtype.kind not in "fiub":
            raise TypeError("Named values require a numerical dtype")
        self.entry_present = (np.ones(len(self.names), bool) if entry_present is None else np.asarray(entry_present))
        if self.entry_present.dtype != bool or self.entry_present.shape != (len(self.names),):
            raise ValueError("Presence must be boolean on the entity axis")

    @classmethod
    def empty(cls, *, component_names: tuple[str, ...]) -> "ChannelValues":
        shape = (0, len(component_names)) if component_names else (0,)
        return cls((), np.empty(shape, dtype=np.float64), component_names=component_names)

    @classmethod
    def from_mapping(cls, values: Mapping, *, component_names: tuple[str, ...]) -> "ChannelValues":
        """Explicit admission for external named inputs; runtime arrays pass through."""
        if isinstance(values, cls):
            if values.component_names != component_names:
                raise ValueError("Input components differ from the declared channel")
            return values
        names = tuple(values)
        return cls(names, np.asarray(tuple(values.values()), dtype=np.float64), component_names=component_names) if names else cls.empty(component_names=component_names)

    def aligned_presence(self, names: tuple[str, ...]) -> np.ndarray:
        if names == self.names:
            return self.entry_present
        indices = _selection(self.names, names)
        result = indices >= 0
        if self.names:
            result &= self.entry_present[np.maximum(indices, 0)]
        return result

    def aligned(self, names: tuple[str, ...]) -> np.ndarray:
        """Gather a declared axis once, filling absent entities with NaN."""
        names = tuple(names)
        if names == self.names:
            if self.entry_present.all():
                return self.data_values
            return np.where(self.entry_present.reshape((-1,) + (1,) * (self.data_values.ndim - 1)), self.data_values, np.nan)
        indices = _selection(self.names, names)
        result = np.full((len(names), *self.data_values.shape[1:]), np.nan, dtype=np.float64)
        found = indices >= 0
        if len(self.names):
            found &= self.entry_present[np.maximum(indices, 0)]
        result[found] = self.data_values[indices[found]]
        return result

    def immutable_copy(self) -> "ChannelValues":
        from freemocap.core.data_tensors.data_tensor import _immutable_values
        return ChannelValues(self.names, _immutable_values(self.data_values), _immutable_values(self.entry_present),
                             component_names=self.component_names)

    def with_values(self, values: np.ndarray, present: np.ndarray | None = None) -> "ChannelValues":
        return ChannelValues(self.names, values, self.entry_present if present is None else present, component_names=self.component_names)

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        column = self._columns.get(name)
        return column is not None and bool(self.entry_present[column])

    def __getitem__(self, name: str) -> np.ndarray | np.generic:
        column = self._columns[name]
        if not self.entry_present[column]:
            raise KeyError(name)
        return self.data_values[column]

    def __iter__(self) -> Iterator[str]:
        return (self.names[column] for column in np.flatnonzero(self.entry_present))

    def __len__(self) -> int:
        return int(np.count_nonzero(self.entry_present))
