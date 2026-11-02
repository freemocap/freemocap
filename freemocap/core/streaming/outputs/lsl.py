"""Publish declared numerical channels and acquisition provenance through LSL.

One fixed-shape numerical outlet per channel identity; one string provenance
outlet per pipeline preserves source nanoseconds without float32/JSON-number
rounding. All outlets for a frame receive the same mapped acquisition instant.
Schema changes fail this output explicitly rather than silently changing columns.
[@lslIntroduction; @lslInternalsOverview; @lslTimeSynchronizationGuide;
 @pylslOutletSource; @pylslInfoSource]
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import json
from typing import Any
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from freemocap.core.streaming.message_model import (
    ChannelBlock, ChannelKind, FrameMessage, ModelDefinition,
)
from freemocap.core.streaming.outputs.contracts import OutputSample  # noqa: TC001 - runtime beartype resolution
from freemocap.core.streaming.outputs.lsl_clock import LslClockMapping


class LslConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stream_name: str = Field(default='FreeMoCap', min_length=1, max_length=128)
    channel_kinds: tuple[ChannelKind, ...] | None = Field(default=None, min_length=1)
    model_ids: tuple[str, ...] | None = Field(default=None, min_length=1)
    max_buffered: int = Field(default=1, ge=1, le=60,
        description='LSL buffer units: 100 samples per unit for these irregular streams.')


def lsl_unavailable_reason() -> str | None:
    if importlib.util.find_spec('pylsl') is None:
        return 'pylsl and its native liblsl runtime are not installed'
    try:
        importlib.import_module('pylsl')
    except (ImportError, OSError, RuntimeError) as error:
        return f'LSL runtime could not be loaded: {error}'
    return None


_SEGMENT_KINDS = frozenset((ChannelKind.SEGMENT_ORIGINS, ChannelKind.ROTATIONS_LOCAL,
    ChannelKind.ROTATIONS_WORLD, ChannelKind.SEGMENT_LENGTHS, ChannelKind.SEGMENT_SCALES))
_LANDMARK_KINDS = frozenset((ChannelKind.LANDMARKS_3D, ChannelKind.MAPPED_KEYPOINTS_3D))
_POSITION_KINDS = frozenset((ChannelKind.KEYPOINTS_3D, ChannelKind.RAW_KEYPOINTS_3D,
    ChannelKind.LANDMARKS_3D, ChannelKind.MAPPED_KEYPOINTS_3D,
    ChannelKind.SEGMENT_ORIGINS, ChannelKind.DERIVED_POINTS))


@dataclass(frozen=True, slots=True)
class LslChannelSchema:
    identity: tuple[str, ...]
    labels: tuple[str, ...]
    units: tuple[str, ...]
    metadata_json: str


def _length_unit(frame: FrameMessage) -> str:
    if frame.diagnostics is not None:
        return 'mm' if frame.diagnostics.length_units == 'millimeters' else 'pixels'
    return frame.convention.units.value


def _unit(kind: ChannelKind, component: str, frame: FrameMessage) -> str:
    if kind in _POSITION_KINDS and component in ('x', 'y', 'z'):
        return _length_unit(frame)
    if kind in (ChannelKind.ROTATIONS_LOCAL, ChannelKind.ROTATIONS_WORLD):
        return 'dimensionless'
    if component == 'radians':
        return 'radians'
    if component == 'length_mm':
        return _length_unit(frame)
    # Do not invent component units that the source does not declare.
    return 'unspecified'


def channel_schema(
    *, frame: FrameMessage, block: ChannelBlock, model: ModelDefinition | None,
    identity: tuple[str, ...],
) -> LslChannelSchema:
    names = block.names
    if names is None:
        if model is None:
            raise ValueError('Numerical channel requires inline names or its declared model')
        if block.kind in _SEGMENT_KINDS:
            names = tuple(segment.name for segment in model.segments)
        elif block.kind in _LANDMARK_KINDS:
            names = tuple(landmark.name for landmark in model.landmarks)
        else:
            raise ValueError(f'{block.kind} does not declare its numerical row identities')
    if not names or not block.columns:
        raise ValueError('LSL numerical channels require nonempty row and component identities')
    if len(block.data) != len(names) * len(block.columns) * 4:
        raise ValueError('Packed float32 values disagree with declared row/component shape')
    labels = tuple(f'{name}.{component}' for name in names for component in block.columns)
    units = tuple(_unit(block.kind, component, frame) for _ in names for component in block.columns)
    if block.sample_status is not None:
        if len(block.sample_status) != len(names) or not block.status_labels:
            raise ValueError('Sample status requires one byte per row and declared labels')
        if max(block.sample_status, default=0) >= len(block.status_labels):
            raise ValueError('Sample status code is not declared by the source')
        labels += tuple(f'{name}.sample_status' for name in names)
        units += ('status_code',) * len(names)
    metadata = {
        'identity': identity, 'kind': block.kind.value, 'row_names': names,
        'components': block.columns, 'sample_status_labels': block.status_labels,
        'sample_status_appended': block.sample_status is not None,
        'numeric_dtype': '<f4', 'order': 'row_major', 'nominal_rate': 'irregular',
        'convention': frame.convention.to_cbor_message(), 'camera_id': block.camera_id,
        'channel_length_units': _length_unit(frame),
        'image_size': block.image_size,
        'model': model.to_cbor_message() if model is not None else None,
    }
    return LslChannelSchema(identity, labels, units,
        json.dumps(metadata, sort_keys=True, separators=(',', ':')))


def _static_signature(block: ChannelBlock, frame: FrameMessage) -> tuple:
    return (block.kind, block.columns, block.names, len(block.data),
        block.sample_status is not None, block.status_labels, block.image_size, _length_unit(frame))


@dataclass
class _PreparedChannel:
    schema: LslChannelSchema
    signature: tuple
    model: ModelDefinition | None
    convention: Any
    outlet: Any


class LslEmitter:
    def __init__(self, config: LslConfig, *, backend: Any = None,
                 clock: LslClockMapping | None = None):
        if backend is None:
            reason = lsl_unavailable_reason()
            if reason is not None:
                raise RuntimeError(reason)
            backend = importlib.import_module('pylsl')
        self.config = config
        self._backend = backend
        self.clock = clock if clock is not None else LslClockMapping.calibrate(backend.local_clock)
        self._session_id = str(uuid4())
        self._channels: dict[tuple[str, ...], _PreparedChannel] = {}
        self._provenance: dict[str, Any] = {}
        self._topologies: dict[str, frozenset[tuple[str, ...]]] = {}
        self._last_frames: dict[str, int] = {}
        self._active_pipeline_id: str | None = None
        self._closed = False

    def _outlet(self, *, name: str, source_id: str, labels: tuple[str, ...],
                units: tuple[str, ...], metadata: str, channel_format: str) -> Any:
        info = self._backend.StreamInfo(name=name, type='FreeMoCap',
            channel_count=len(labels), nominal_srate=0.0,
            channel_format=channel_format, source_id=source_id)
        desc = info.desc()
        desc.append_child_value('freemocap_metadata', metadata)
        desc.append_child_value('acquisition_clock', 'SkellyCam perf_counter_ns')
        desc.append_child_value('perf_counter_anchor_ns', str(self.clock.perf_counter_anchor_ns))
        desc.append_child_value('lsl_anchor_s', repr(self.clock.lsl_anchor_s))
        desc.append_child_value('clock_calibration_span_ns', str(self.clock.calibration_span_ns))
        channels = desc.append_child('channels')
        for label, unit in zip(labels, units, strict=True):
            channel = channels.append_child('channel')
            channel.append_child_value('label', label)
            channel.append_child_value('unit', unit)
        return self._backend.StreamOutlet(info, chunk_size=0, max_buffered=self.config.max_buffered)

    def emit(self, sample: OutputSample) -> None:
        if self._closed:
            raise RuntimeError('LSL output is closed')
        timestamp = self.clock.to_lsl_seconds(sample.source_timestamp_ns)
        if timestamp == 0.0:
            # pylsl uses zero as a sentinel for local_clock() at push time.
            raise ValueError('Mapped acquisition timestamp is the LSL automatic-time sentinel')
        if sample.pipeline_id != self._active_pipeline_id:
            # The manager selects one source per output. Capture restarts retire
            # its old native outlets and metadata; receivers discover new streams.
            self._release_outlets()
            self._session_id = str(uuid4())
            self._active_pipeline_id = sample.pipeline_id
        last_frame = self._last_frames.get(sample.pipeline_id)
        if last_frame is not None and sample.frame.frame_number <= last_frame:
            raise ValueError('LSL source frame order must increase within a pipeline')
        models = {model.model_id: model for model in sample.frame.models}
        selected = []
        for owner_type, owners in (('instance', sample.frame.instances), ('tracker', sample.frame.trackers)):
            for owner in owners:
                if self.config.model_ids is not None and owner.model_id not in self.config.model_ids:
                    continue
                owner_id = str(owner.instance_id) if owner_type == 'instance' else owner.tracker_id
                for block in owner.channels:
                    if self.config.channel_kinds is not None and block.kind not in self.config.channel_kinds:
                        continue
                    identity = (sample.pipeline_id, owner_type, owner_id, owner.model_id,
                        block.kind.value, block.camera_id or '')
                    model = models.get(owner.model_id)
                    existing = self._channels.get(identity)
                    signature = _static_signature(block, sample.frame)
                    if (existing is not None and existing.signature == signature
                            and existing.model is model and existing.convention is sample.frame.convention):
                        schema = existing.schema
                    else:
                        schema = channel_schema(frame=sample.frame, block=block, model=model, identity=identity)
                        if existing is not None and existing.schema != schema:
                            raise ValueError('LSL channel schema changed; stop and restart this output')
                    # Status codes are dynamic, so validate each sample even when
                    # its immutable descriptor was prepared earlier.
                    if block.sample_status is not None:
                        count = len(block.data) // (4 * len(block.columns))
                        if (len(block.sample_status) != count or not block.status_labels
                                or max(block.sample_status, default=0) >= len(block.status_labels)):
                            raise ValueError('LSL sample status disagrees with declared schema')
                    selected.append((identity, block, model, schema, signature))
        identities = frozenset(item[0] for item in selected)
        if not selected:
            raise ValueError('No requested numerical channels are available in this source frame')
        if len(identities) != len(selected):
            raise ValueError('Duplicate numerical channel identity in source frame')
        previous = self._topologies.get(sample.pipeline_id)
        if previous is not None and identities != previous:
            raise ValueError('LSL stream topology changed; stop and restart this output')

        # Validate the entire frame before publishing any of its numerical samples.
        for identity, block, model, schema, signature in selected:
            prepared = self._channels.get(identity)
            if prepared is None:
                encoded_identity = json.dumps(identity, separators=(',', ':'))
                outlet = self._outlet(name=f'{self.config.stream_name}:{identity[4]}',
                    source_id=f'{self._session_id}:{encoded_identity}', labels=schema.labels,
                    units=schema.units, metadata=schema.metadata_json, channel_format='float32')
                prepared = _PreparedChannel(schema, signature, model, sample.frame.convention, outlet)
                self._channels[identity] = prepared
            values = np.frombuffer(block.data, dtype='<f4')
            if block.sample_status is not None:
                values = np.concatenate((values, np.frombuffer(block.sample_status, dtype=np.uint8)))
            prepared.outlet.push_sample(values, timestamp=timestamp)
            prepared.model = model
            prepared.convention = sample.frame.convention

        if sample.pipeline_id not in self._provenance:
            self._provenance[sample.pipeline_id] = self._outlet(
                name=f'{self.config.stream_name}:acquisition',
                source_id=f'{self._session_id}:{sample.pipeline_id}:acquisition',
                labels=('acquisition_provenance',), units=('json',),
                metadata=json.dumps({'nanoseconds': 'decimal strings; preserve exact source values',
                    'numeric_samples': 'same mapped acquisition timestamp',
                    'source_frame_gaps': 'source sequence gaps, not an estimate of network loss'}),
                channel_format='string')
        provenance = json.dumps({
            'pipeline_id': sample.pipeline_id,
            'frame_number': sample.frame.frame_number,
            'source_timestamp_ns': str(sample.source_timestamp_ns),
            'camera_timestamps_ns': {camera: str(value) for camera, value in sample.camera_timestamps_ns},
            'source_frame_gap': 0 if last_frame is None else sample.frame.frame_number - last_frame - 1,
        }, separators=(',', ':'))
        # This follows successful numeric pushes; it is not a claim of atomic
        # delivery across outlets. Receiver tests must reconcile sample counts.
        self._provenance[sample.pipeline_id].push_sample([provenance], timestamp=timestamp)
        self._topologies[sample.pipeline_id] = identities
        self._last_frames[sample.pipeline_id] = sample.frame.frame_number

    def close(self) -> None:
        self._closed = True
        self._release_outlets()

    def _release_outlets(self) -> None:
        # pylsl owns native outlet destruction through object lifetime. Do not
        # invoke __del__ manually: that would destroy the same handle twice.
        self._channels.clear()
        self._provenance.clear()
        self._topologies.clear()
        self._last_frames.clear()
        self._active_pipeline_id = None
