"""Collect existing scientific tensors without rebuilding or copying their values."""

from dataclasses import dataclass, field
import json
from types import MappingProxyType
from typing import Mapping

import numpy as np

from freemocap.core.data_tensors.data_tensor import DataTensor
from freemocap.core.data_tensors.layout_definitions import SourceIdentity
from freemocap.core.data_tensors.sample_timeline import SampleTimeline
from freemocap.core.data_tensors.time_series import TimeSeries


@dataclass(frozen=True, slots=True)
class ChannelIdentity:
    """One scientific channel within a recording run, independent of array shape."""

    source_identity: SourceIdentity
    channel_kind: str
    reference_id: str | None
    static_data: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("Channel source identity must be declared")
        if not isinstance(self.channel_kind, str) or not self.channel_kind.strip():
            raise ValueError("Channel kind must be a nonempty string")
        if self.reference_id is not None and (not isinstance(self.reference_id, str) or not self.reference_id.strip()):
            raise ValueError("Reference identity must be nonempty when supplied")
        if type(self.static_data) is not bool:
            raise TypeError("Static-data status must be boolean")

    @classmethod
    def from_data(cls, data: DataTensor | TimeSeries) -> "ChannelIdentity":
        tensor = data.data_tensor if isinstance(data, TimeSeries) else data
        layout = tensor.tensor_layout
        if layout.source_identity is None or layout.channel_kind is None:
            raise ValueError("Dataset channels require source identity and channel kind")
        return cls(layout.source_identity, layout.channel_kind, layout.reference_id, isinstance(data, DataTensor))


def _reject_constant(value: str) -> None:
    raise ValueError(f"Definition JSON contains non-finite constant {value}")


@dataclass(frozen=True, slots=True)
class DefinitionDocument:
    """One immutable serialized model, reference or provenance definition.

    The owning scientific schema remains responsible for its contents. JSON is
    validated here without retaining mutable dictionaries or per-frame copies.
    """

    definition_id: str
    content_json: str

    def __post_init__(self) -> None:
        if not isinstance(self.definition_id, str) or not self.definition_id.strip():
            raise ValueError("Definition identity must be a nonempty string")
        if not isinstance(self.content_json, str):
            raise TypeError("Definition content must be immutable JSON text")
        json.loads(self.content_json, parse_constant=_reject_constant)


@dataclass(frozen=True, slots=True, eq=False)
class RecordingDataset:
    """Selected channels from one recording run, retaining independent timelines.

    Assembly and selection retain existing immutable tensor objects. There is no
    numerical concatenation, resampling, implicit clock alignment or payload scan.
    Each channel supplies one selected sample range; this is not a chunk store.
    """

    recording_id: str
    run_id: int
    time_series: tuple[TimeSeries, ...] = ()
    static_tensors: tuple[DataTensor, ...] = ()
    definition_documents: tuple[DefinitionDocument, ...] = ()
    _channel_index: Mapping[ChannelIdentity, DataTensor | TimeSeries] = field(init=False, repr=False)
    _sample_timelines: tuple[SampleTimeline, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.recording_id, str) or not self.recording_id.strip():
            raise ValueError("Recording identity must be a nonempty string")
        if type(self.run_id) is not int or self.run_id < 0:
            raise ValueError("Run ID must be a nonnegative integer")
        series = tuple(self.time_series)
        static = tuple(self.static_tensors)
        documents = tuple(self.definition_documents)
        if len({item.definition_id for item in documents}) != len(documents):
            raise ValueError("Dataset definition identities must be unique")
        channels = {}
        scientific_keys = set()
        timelines = {}
        sample_axes = {"sample_identity", *(item.sample_axis_name for item in series)}
        for item in (*series, *static):
            if not item.is_immutable:
                raise ValueError("Dataset channels require immutable_copy() before assembly")
            identity = ChannelIdentity.from_data(item)
            scientific_key = (identity.source_identity, identity.channel_kind, identity.reference_id)
            if scientific_key in scientific_keys:
                raise ValueError("Duplicate scientific channel, including static/dynamic ambiguity")
            scientific_keys.add(scientific_key)
            channels[identity] = item
            if isinstance(item, DataTensor):
                if any(axis.axis_name in sample_axes for axis in item.tensor_layout.axes):
                    raise ValueError("Static tensor must not declare a sample axis")
                continue
            timeline = item.sample_timeline
            previous = timelines.get(timeline.timeline_id)
            if previous is not None and previous is not timeline:
                if (
                    previous.clock_id != timeline.clock_id
                    or previous.clock_epoch != timeline.clock_epoch
                    or previous.source_identity != timeline.source_identity
                    or not np.array_equal(previous.sample_ids, timeline.sample_ids)
                    or not np.array_equal(previous.timestamps_s, timeline.timestamps_s)
                ):
                    raise ValueError(f"Conflicting sample timeline identity {timeline.timeline_id!r}")
            else:
                timelines[timeline.timeline_id] = timeline
        object.__setattr__(self, "time_series", series)
        object.__setattr__(self, "static_tensors", static)
        object.__setattr__(self, "definition_documents", documents)
        object.__setattr__(self, "_channel_index", MappingProxyType(channels))
        object.__setattr__(self, "_sample_timelines", tuple(timelines.values()))

    @property
    def channel_identities(self) -> tuple[ChannelIdentity, ...]:
        return tuple(self._channel_index)

    @property
    def sample_timelines(self) -> tuple[SampleTimeline, ...]:
        return self._sample_timelines

    def channel_data(self, channel_identity: ChannelIdentity) -> DataTensor | TimeSeries:
        """Return the exact stored object; unknown identity raises KeyError."""
        return self._channel_index[channel_identity]

    def select_channels(self, channel_identities: tuple[ChannelIdentity, ...]) -> "RecordingDataset":
        """Retain selected channel objects and shared definitions without data copies."""
        selected = tuple(self.channel_data(identity) for identity in channel_identities)
        return RecordingDataset(
            recording_id=self.recording_id, run_id=self.run_id,
            time_series=tuple(item for item in selected if isinstance(item, TimeSeries)),
            static_tensors=tuple(item for item in selected if isinstance(item, DataTensor)),
            definition_documents=self.definition_documents,
        )
