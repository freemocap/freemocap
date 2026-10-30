"""Saved-channel metadata and array adapters, independent of Parquet I/O imports."""
from dataclasses import dataclass

import numpy as np

from skellyforge.core.data_tensors.layout_definitions import AxisDefinition, SourceIdentity, TensorLayout
from skellyforge.core.data_tensors.data_tensor import CompanionTensor, DataTensor, ScientificProvenance
from skellyforge.core.data_tensors.sample_timing import SampleTiming
from skellyforge.core.data_tensors.time_series import TimeSeries
from freemocap.core.recording.parquet_storage.channel_selection import ChannelSelection


@dataclass(frozen=True)
class ChannelArrays:
    context: ChannelSelection
    names: tuple[str, ...]
    components: tuple[str, ...]
    units: tuple[str, ...]
    frames: np.ndarray
    timestamps: np.ndarray
    values: np.ndarray
    present: np.ndarray
    source_components: tuple[str, ...] | None = None

    def to_data_tensor(
        self, *, scientific_provenance: ScientificProvenance,
        source_identity: SourceIdentity | None = None,
    ) -> DataTensor:
        """Bind saved channel identities without copying its numerical buffers.

        Owned arrays outlive the reader. Scratch-backed arrays have the lifetime
        of read_channel_arrays; publish an owned copy before leaving that context.
        """
        if source_identity is None:
            source_identity = SourceIdentity(source_id=self.context.source, sensor_group=self.context.sensor_group)
        if (source_identity.source_id != self.context.source
                or source_identity.sensor_group != self.context.sensor_group):
            raise ValueError("Tensor source identity disagrees with the saved channel")
        entity_axes = (
            AxisDefinition("entity_identity", self.names),
            AxisDefinition("component_identity", self.components if self.source_components is None else self.source_components),
        )
        tensor_axes = entity_axes if self.context.static else (AxisDefinition("sample_identity", self.frames), *entity_axes)
        layout = TensorLayout(axes=tensor_axes, dtype=self.values.dtype, component_units=self.units,
            reference_id=self.context.reference_frame, source_identity=source_identity, channel_kind=self.context.channel)
        presence = CompanionTensor(metadata_name="entry_presence", data_values=self.present,
                                   tensor_layout=TensorLayout(axes=tensor_axes, dtype=bool))
        return DataTensor(data_values=self.values, tensor_layout=layout,
                          scientific_provenance=scientific_provenance, companion_tensors=(presence,))

    def to_time_series(
        self, *, sample_timing: SampleTiming, scientific_provenance: ScientificProvenance,
        source_identity: SourceIdentity | None = None,
    ) -> TimeSeries:
        """Bind exact saved sampling; matching counts alone do not establish timing."""
        if self.context.static:
            raise ValueError("Static fits have no sample timing")
        if (not np.array_equal(self.frames, sample_timing.sample_ids)
                or not np.array_equal(self.timestamps, sample_timing.timestamps_s)):
            raise ValueError("Sample timing differs from saved channel IDs or timestamps")
        return TimeSeries(data_tensor=self.to_data_tensor(scientific_provenance=scientific_provenance,
                          source_identity=source_identity), sample_timing=sample_timing)

    def descriptor(self):
        return dict(context=self.context.model_dump(mode='json'), names=self.names,
            components=self.components, source_components=self.source_components or self.components,
            units=self.units, shape=list(self.values.shape),
            axes=['names', 'components'] if self.context.static else ['frames', 'names', 'components'],
            missing_values='NaN; present distinguishes recorded null from absent row')
