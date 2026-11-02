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
import queue
import threading
from typing import Any
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from freemocap.core.streaming.channel_helpers import TEMPORAL_STATUS_LABELS
from freemocap.core.streaming.message_model import (
    ChannelBlock, ChannelKind, FrameMessage, ModelDefinition,
)
from freemocap.core.streaming.outputs.contracts import OutputEmission, OutputSample  # noqa: TC001 - runtime beartype resolution
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
    ChannelKind.ROTATIONS_WORLD, ChannelKind.SEGMENT_LENGTHS, ChannelKind.SEGMENT_SCALES,
    ChannelKind.OVERLAY_REPROJECTIONS))
_PIXEL_KINDS = frozenset((ChannelKind.OVERLAY_2D, ChannelKind.OVERLAY_REPROJECTIONS, ChannelKind.BOXES_2D))
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


def _length_unit(frame: FrameMessage, kind: ChannelKind) -> str:
    # Camera projections stay in capture pixels even when the fitted model is mm.
    if kind in _PIXEL_KINDS:
        return 'pixels'
    if frame.diagnostics is not None:
        return 'mm' if frame.diagnostics.length_units == 'millimeters' else 'pixels'
    return frame.convention.units.value


def _unit(kind: ChannelKind, component: str, frame: FrameMessage) -> str:
    if kind in _PIXEL_KINDS and component in ('x', 'y', 'x1', 'y1', 'x2', 'y2'):
        return 'pixels'
    if kind in _POSITION_KINDS and component in ('x', 'y', 'z'):
        return _length_unit(frame, kind)
    if kind in (ChannelKind.ROTATIONS_LOCAL, ChannelKind.ROTATIONS_WORLD):
        return 'dimensionless'
    if component == 'radians':
        return 'radians'
    if component == 'length_mm':
        return _length_unit(frame, kind)
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
    _validate_status(block, len(names), identity)
    labels += tuple(f'{name}.sample_status' for name in names)
    units += ('status_code',) * len(names)
    metadata = {
        'identity': identity, 'kind': block.kind.value, 'row_names': names,
        'components': block.columns, 'sample_status_labels': TEMPORAL_STATUS_LABELS,
        'sample_status_appended': True,
        'sample_status_absent': 'NaN: source did not declare row status',
        'sample_status_layout': 'after all numeric components, one value per row in row_names order',
        'projection_version': 2,
        'numeric_dtype': '<f4', 'order': 'row_major', 'nominal_rate': 'irregular',
        'convention': frame.convention.to_cbor_message(), 'camera_id': block.camera_id,
        'channel_length_units': _length_unit(frame, block.kind),
        'image_size': block.image_size,
        'model': model.to_cbor_message() if model is not None else None,
    }
    return LslChannelSchema(identity, labels, units,
        json.dumps(metadata, sort_keys=True, separators=(',', ':')))


def _validate_status(block: ChannelBlock, count: int, identity: tuple[str, ...]) -> None:
    # Use the source contract's vocabulary, including for frames that omit status.
    # An absent declaration is unknown, not evidence of current observations.
    if block.status_labels is not None and block.status_labels != TEMPORAL_STATUS_LABELS:
        raise ValueError(f'LSL status vocabulary changed or unsupported for {identity!r}: status_labels')
    if block.sample_status is not None and (
            len(block.sample_status) != count or block.status_labels is None
            or max(block.sample_status, default=0) >= len(TEMPORAL_STATUS_LABELS)):
        raise ValueError(f'LSL sample status disagrees with declared schema for {identity!r}')


def _schema_change_error(before: LslChannelSchema, after: LslChannelSchema) -> ValueError:
    fields = [field for field in ('labels', 'units') if getattr(before, field) != getattr(after, field)]
    old, new = json.loads(before.metadata_json), json.loads(after.metadata_json)
    fields.extend(f'metadata.{key}' for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key))
    return ValueError(f'LSL channel schema changed for {after.identity!r}: '
                     f'{", ".join(fields)}; stop and restart this output')


def _static_signature(block: ChannelBlock, frame: FrameMessage) -> tuple:
    return (block.kind, block.columns, block.names, len(block.data),
        block.image_size, _length_unit(frame, block.kind))


@dataclass
class _PreparedChannel:
    schema: LslChannelSchema
    signature: tuple
    model: ModelDefinition | None
    convention: Any
    outlet: Any


@dataclass(frozen=True, slots=True)
class _ChannelAdvertisement:
    schema: LslChannelSchema
    signature: tuple
    model: ModelDefinition | None
    convention: Any


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
        self._preparing = False
        self._models: dict[str, ModelDefinition] = {}
        self._pending: dict[tuple[str, ...], _ChannelAdvertisement] = {}
        self._advertise_requests: queue.Queue = queue.Queue(maxsize=1)
        self._advertise_results: queue.SimpleQueue = queue.SimpleQueue()
        self._advertise_stop = threading.Event()
        self._advertise_thread: threading.Thread | None = None

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

    def _create_channel(self, descriptor: _ChannelAdvertisement) -> _PreparedChannel:
        schema = descriptor.schema
        encoded_identity = json.dumps(schema.identity, separators=(',', ':'))
        outlet = self._outlet(name=f'{self.config.stream_name}:{schema.identity[4]}',
            source_id=f'{self._session_id}:{encoded_identity}', labels=schema.labels,
            units=schema.units, metadata=schema.metadata_json, channel_format='float32')
        return _PreparedChannel(schema, descriptor.signature, descriptor.model, descriptor.convention, outlet)

    def _advertise_loop(self) -> None:
        while not self._advertise_stop.is_set():
            try:
                descriptors = self._advertise_requests.get(timeout=.05)
            except queue.Empty:
                continue
            for descriptor in descriptors:
                if self._advertise_stop.is_set():
                    return
                try:
                    prepared = self._create_channel(descriptor)
                except BaseException as error:
                    self._advertise_results.put((descriptor.schema.identity, None, error))
                    return
                self._advertise_results.put((descriptor.schema.identity, prepared, None))
                # The result queue now owns the handle; do not retain an extra
                # reference while waiting for the next advertisement request.
                del prepared

    def _adopt_advertisements(self) -> None:
        while True:
            try:
                identity, prepared, error = self._advertise_results.get_nowait()
            except queue.Empty:
                return
            if error is not None:
                raise RuntimeError(f'LSL outlet advertisement failed for {identity!r}: {error}') from error
            self._channels[identity] = prepared
            self._pending.pop(identity)

    def _schedule_advertisements(self, descriptors: tuple[_ChannelAdvertisement, ...]) -> bool:
        if not descriptors:
            return False
        if self._advertise_thread is None:
            self._advertise_stop.clear()
            self._advertise_thread = threading.Thread(target=self._advertise_loop,
                name=f'lsl-advertise-{self._session_id[:8]}', daemon=True)
            self._advertise_thread.start()
        try:
            self._advertise_requests.put_nowait(descriptors)
        except queue.Full:
            # Current samples continue; only a later source frame may retry.
            # Never retain numerical frames or grow an advertisement backlog.
            return True
        self._pending.update((descriptor.schema.identity, descriptor) for descriptor in descriptors)
        return False

    def prepare(self, sample: OutputSample) -> OutputEmission:
        """Advertise the schema without publishing the preparation frame."""
        self._preparing = True
        try:
            return self.emit(sample)
        except BaseException:
            self._release_outlets()
            raise
        finally:
            self._preparing = False

    def emit(self, sample: OutputSample) -> OutputEmission:
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
        self._adopt_advertisements()
        models = {}
        for model in sample.frame.models:
            cached = self._models.get(model.model_id)
            # Reconcile equal immutable metadata once per model, not per outlet.
            # Every source message remains independently self-describing.
            models[model.model_id] = cached if cached is not None and (cached is model or cached == model) else model
        self._models = models
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
                    existing = self._channels.get(identity) or self._pending.get(identity)
                    signature = _static_signature(block, sample.frame)
                    if (existing is not None and existing.signature == signature
                            and existing.model is model and existing.convention == sample.frame.convention):
                        schema = existing.schema
                    else:
                        schema = channel_schema(frame=sample.frame, block=block, model=model, identity=identity)
                        if existing is not None and existing.schema != schema:
                            raise _schema_change_error(existing.schema, schema)
                    # Status codes are dynamic, so validate each sample even when
                    # its immutable descriptor was prepared earlier.
                    _validate_status(block, len(block.data) // (4 * len(block.columns)), identity)
                    selected.append((identity, block, model, schema, signature))
        identities = frozenset(item[0] for item in selected)
        if len(identities) != len(selected):
            raise ValueError('Duplicate numerical channel identity in source frame')
        # Availability is per frame. A returning identity must retain its exact
        # schema; an explicitly declared new identity gets a separate outlet.
        descriptors = tuple(_ChannelAdvertisement(schema, signature, model, sample.frame.convention)
                            for identity, block, model, schema, signature in selected
                            if identity not in self._channels and identity not in self._pending)
        saturated = False
        if self._preparing or sample.pipeline_id not in self._provenance:
            for descriptor in descriptors:
                self._channels[descriptor.schema.identity] = self._create_channel(descriptor)
        else:
            saturated = self._schedule_advertisements(descriptors)
        if sample.pipeline_id not in self._provenance:
            self._provenance[sample.pipeline_id] = self._outlet(
                name=f'{self.config.stream_name}:acquisition',
                source_id=f'{self._session_id}:{sample.pipeline_id}:acquisition',
                labels=('acquisition_provenance',), units=('json',),
                metadata=json.dumps({'nanoseconds': 'decimal strings; preserve exact source values',
                    'numeric_samples': 'same mapped acquisition timestamp',
                    'source_frame_gaps': 'source sequence gaps, not an estimate of network loss',
                    'channel_coverage': {
                        'available': 'selected blocks declared in this source frame',
                        'absent': 'previously declared identities missing from this source frame; no numerical sample',
                        'preparing': 'descriptor accepted for advertisement; no historical samples retained',
                        'deferred': 'advertisement queue full; retry only if a later source frame declares the block',
                        'published': 'current numerical samples pushed to subscribed outlets',
                        'unsubscribed': 'current blocks with ready outlets but no receiver',
                        'status_declared': 'source explicitly supplied per-row status bytes',
                    }}),
                channel_format='string')
        self._topologies[sample.pipeline_id] = self._topologies.get(sample.pipeline_id, frozenset()) | identities
        if self._preparing:
            return OutputEmission(False, 'waiting_for_receiver', len(self._channels) + 1, 0)
        # Each outlet has independent subscribers. Connectivity is not recording.
        # Never queue pre-subscription samples. [@lslOutletConsumerReadiness]
        connected = {identity for identity, prepared in self._channels.items()
                     if prepared.outlet.have_consumers()}
        published = connected & identities
        provenance_outlet = self._provenance[sample.pipeline_id]
        provenance_connected = provenance_outlet.have_consumers()
        for identity, block, model, schema, signature in selected:
            if identity not in published:
                continue
            prepared = self._channels[identity]
            values = np.frombuffer(block.data, dtype='<f4')
            count = len(values) // len(block.columns)
            statuses = (np.full(count, np.nan, dtype=np.float32) if block.sample_status is None
                        else np.frombuffer(block.sample_status, dtype=np.uint8))
            values = np.concatenate((values, statuses))
            prepared.outlet.push_sample(values, timestamp=timestamp)
            prepared.model = model
            prepared.convention = sample.frame.convention

        provenance = json.dumps({
            'pipeline_id': sample.pipeline_id,
            'frame_number': sample.frame.frame_number,
            'source_timestamp_ns': str(sample.source_timestamp_ns),
            'camera_timestamps_ns': {camera: str(value) for camera, value in sample.camera_timestamps_ns},
            'source_frame_gap': 0 if last_frame is None else sample.frame.frame_number - last_frame - 1,
            'available_channel_identities': sorted(identities),
            'absent_channel_identities': sorted(self._topologies[sample.pipeline_id] - identities),
            'preparing_channel_identities': sorted(identities & self._pending.keys()),
            'deferred_channel_identities': sorted(identities - self._channels.keys() - self._pending.keys()),
            'advertisement_queue_saturated': saturated,
            'published_channel_identities': sorted(published),
            'status_declared_channel_identities': sorted(identity for identity, block, *_ in selected
                                                        if block.sample_status is not None),
            'unsubscribed_channel_identities': sorted((identities & self._channels.keys()) - connected),
        }, separators=(',', ':'))
        # This follows successful numeric pushes; it is not a claim of atomic
        # delivery across outlets. Receiver tests must reconcile sample counts.
        if provenance_connected:
            provenance_outlet.push_sample([provenance], timestamp=timestamp)
        self._topologies[sample.pipeline_id] = self._topologies.get(sample.pipeline_id, frozenset()) | identities
        self._last_frames[sample.pipeline_id] = sample.frame.frame_number
        connected_count = len(connected) + int(provenance_connected)
        return OutputEmission(bool(published) or provenance_connected,
            'sending' if connected_count else 'waiting_for_receiver',
            len(self._channels) + 1, connected_count)

    def close(self) -> None:
        self._closed = True
        self._release_outlets()

    def _release_outlets(self) -> None:
        self._advertise_stop.set()
        if self._advertise_thread is not None:
            # Native construction is not interruptible. Wait for the in-flight
            # call before releasing its result and changing source/session IDs.
            self._advertise_thread.join()
            self._advertise_thread = None
        for pending_queue in (self._advertise_requests, self._advertise_results):
            while True:
                try:
                    pending_queue.get_nowait()
                except queue.Empty:
                    break
        self._pending.clear()
        # pylsl owns native outlet destruction through object lifetime. Do not
        # invoke __del__ manually: that would destroy the same handle twice.
        self._channels.clear()
        self._models.clear()
        self._provenance.clear()
        self._topologies.clear()
        self._last_frames.clear()
        self._active_pipeline_id = None
