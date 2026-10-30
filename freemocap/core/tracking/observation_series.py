"""Camera predictions with recording tensors and inexpensive frame views.

The storage retains every authored component. The current image-plane adapter
projects x/y into Tracker's XYZ schema and supplies its unused Z coordinate.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from operator import index as integer_index

import numpy as np

from skellyforge.core.data_tensors.data_tensor import ScientificProvenance
from skellyforge.core.data_tensors.layout_definitions import SourceIdentity
from skellyforge.core.data_tensors.sample_timing import SampleTiming
from skellyforge.core.data_tensors.time_series import TimeSeries
from freemocap.core.recording.parquet_storage.channel_arrays import ChannelArrays


@dataclass(frozen=True)
class ObservationSeries:
    camera_id: str
    image_size: tuple[int, int]
    channel_arrays: ChannelArrays
    time_series: TimeSeries = field(init=False, repr=False)
    frame_numbers: tuple[int, ...] = field(init=False)
    stage_names: tuple[str, ...] = field(init=False)
    stage_indices: dict[str, tuple[int, ...]] = field(init=False, repr=False)

    def __post_init__(self):
        arrays = self.channel_arrays
        object.__setattr__(self, 'frame_numbers', tuple(arrays.frames.tolist()))
        stages = tuple(dict.fromkeys(name.partition('.')[0] for name in arrays.names))
        object.__setattr__(self, 'stage_names', stages)
        object.__setattr__(self, 'stage_indices', {stage: tuple(i for i, name in enumerate(arrays.names)
            if name.partition('.')[0] == stage) for stage in stages})
        required = {'x': 'px', 'y': 'px', 'visibility': '1'}
        if any(name not in arrays.components or arrays.units[arrays.components.index(name)] != unit
               for name, unit in required.items()):
            raise ValueError('Saved image predictions require pixel x/y and dimensionless visibility')
        if any('.' not in name for name in arrays.names):
            raise ValueError('Saved observation name has no detector stage')
        identity = SourceIdentity(source_id=arrays.context.source, sensor_group=arrays.context.sensor_group, camera_id=self.camera_id)
        timeline = SampleTiming(timeline_id=f'{arrays.context.sensor_group}:{self.camera_id}',
            clock_id=f'camera:{self.camera_id}', source_identity=identity,
            sample_ids=arrays.frames, timestamps_s=arrays.timestamps)
        object.__setattr__(self, 'time_series', arrays.to_time_series(sample_timing=timeline,
            scientific_provenance=ScientificProvenance(meaning='saved image predictions',
                operation_id='saved_observations', input_refs=(arrays.context.source,)), source_identity=identity))

    @property
    def point_names(self):
        return self.channel_arrays.names

    @property
    def timestamps_s(self):
        return self.channel_arrays.timestamps

    def __len__(self):
        return len(self.channel_arrays.frames)

    def __getitem__(self, index):
        index = integer_index(index)
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        return ObservationFrame(self, index)

    def tracker_coordinates(self, selection=slice(None), *, point_indices=None):
        from freemocap.core.tracking.observation_arrays import TRACKER_COMPONENTS
        arrays = self.channel_arrays
        values = arrays.values[selection]
        shape = values.shape[:-1] if point_indices is None else (*values.shape[:-2], len(point_indices))
        xyz = np.zeros((*shape, len(TRACKER_COMPONENTS)), dtype=np.float64)
        for component in ('x', 'y'):
            component_values = values[..., arrays.components.index(component)]
            xyz[..., TRACKER_COMPONENTS.index(component)] = (component_values if point_indices is None
                else component_values[..., point_indices])
        return xyz

    def confidence_scores(self, selection=slice(None)):
        return self.channel_arrays.values[selection, ..., self.channel_arrays.components.index('visibility')]

    def annotation_frame(self, index):
        """Explicit one-frame Tracker adapter, used only immediately before drawing."""
        from skellytracker.core.data_primitives.keypoints import Keypoints
        from skellytracker.core.data_primitives.observation import Observation, StageObservation
        frame = self[index]
        xyz, visibility = self.tracker_coordinates(index), self.confidence_scores(index)
        stages = {}
        for stage in self.stage_names:
            indices = list(self.stage_indices[stage])
            stages[stage] = StageObservation(name=stage, keypoints=Keypoints(
                names=tuple(self.point_names[i].partition('.')[2] for i in indices),
                xyz=xyz[indices].copy(), visibility=visibility[indices].copy()))
        return Observation(frame_number=frame.frame_number, image_size=self.image_size,
                           timestamp=frame.timestamp, stages=stages)


class RecordingObservationSeries:
    """Recording-owned arrays populated once per camera frame.

    Layout metadata is shared across frames. Numerical storage grows only when
    a previously unseen point/stage or larger box count arrives, never per frame.
    Tracker objects are borrowed during admission and are not retained.
    """
    coordinate_components = ('x', 'y', 'z')  # Tracker's declared Keypoints schema.
    box_components = ('x1', 'y1', 'x2', 'y2', 'confidence')

    def __init__(self, *, camera_id: str, image_size: tuple[int, int],
                 frame_numbers: tuple[int, ...], timestamps_s: tuple[float, ...]):
        if len(frame_numbers) != len(timestamps_s):
            raise ValueError('Observation timing must cover declared frames')
        self.camera_id, self.image_size = camera_id, image_size
        self.frame_numbers = frame_numbers
        self.timestamps_s = np.asarray(timestamps_s, dtype=np.float64)
        self.point_names: tuple[str, ...] = ()
        self.stage_names: tuple[str, ...] = ()
        self.stage_indices: dict[str, tuple[int, ...]] = {}
        count = len(frame_numbers)
        self.coordinate_values = np.full((count, 0, len(self.coordinate_components)), np.nan)
        self.confidence_values = np.zeros((count, 0))
        self.box_values = np.full((count, 0, 0, len(self.box_components)), np.nan)
        self.box_counts = np.zeros((count, 0), dtype=np.intp)
        self.detector_values = np.zeros((count, 0), dtype=bool)
        self.delivered = np.zeros(count, dtype=bool)
        self.observation_timestamps = np.zeros(count)
        self.timestamp_present = np.zeros(count, dtype=bool)
        self.layout_indices = np.full(count, -1, dtype=np.intp)
        self.stage_paths: tuple[tuple[str, ...], ...] = ()
        self.layouts: list[tuple] = []
        self._layout_plans: list[tuple] = []
        self._layout_lookup: dict[tuple, int] = {}
        self._layout_point_names: list[tuple[str, ...]] = []
        self.finalized = False

    def __len__(self):
        return len(self.frame_numbers)

    def __getitem__(self, index):
        index = integer_index(index)
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        if not self.delivered[index]:
            raise ValueError('Observation frame has not been delivered')
        return ObservationFrame(self, index)

    def _grow(self, shape, old, fill):
        values = np.full(shape, fill, dtype=old.dtype)
        values[tuple(slice(0, size) for size in old.shape)] = old
        return values

    def store(self, index: int, observation) -> None:
        from freemocap.core.tracking.observation_arrays import observation_point_names, point_selection, qualified_point_names
        if self.finalized:
            raise ValueError('Completed observation series cannot accept new frames')
        index = integer_index(index)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        if observation.frame_number != self.frame_numbers[index] or observation.image_size != self.image_size:
            raise ValueError('Observation frame/image identity differs from its source')
        if self.delivered[index]:
            raise ValueError('Duplicate camera/frame result')
        names = observation_point_names(observation)
        observed_timestamp = None if observation.timestamp is None else float(observation.timestamp)
        stages = []
        box_rows = []
        def visit(children, parent=()):
            for key, stage in children.items():
                path = (*parent, key)
                if stage.keypoints is not None:
                    points = stage.keypoints
                    if points.xyz.shape != (len(points.names), len(self.coordinate_components)) or points.visibility.shape != (len(points.names),):
                        raise ValueError('Tracker coordinates/confidence differ from declared names')
                    if points.xyz.dtype.kind not in 'fiu' or points.visibility.dtype.kind not in 'fiub':
                        raise ValueError('Tracker coordinates/confidence must be real numerical arrays')
                stages.append((path, stage))
                box_rows.append(np.asarray([(box.x1, box.y1, box.x2, box.y2, box.confidence)
                    for box in stage.bounding_boxes], dtype=np.float64).reshape(-1, len(self.box_components)))
                visit(stage.children, path)
        visit(observation.stages)
        layout = tuple((path, stage.name, None if stage.keypoints is None else stage.keypoints.names)
                       for path, stage in stages)
        layout_index = self._layout_lookup.get(layout)
        point_names = self.point_names if layout_index is not None else tuple(dict.fromkeys((*self.point_names, *names)))
        paths = self.stage_paths if layout_index is not None else tuple(dict.fromkeys((*self.stage_paths, *(path for path, _ in stages))))
        box_count = max((len(stage.bounding_boxes) for _, stage in stages), default=0)
        if point_names != self.point_names:
            self.coordinate_values = self._grow((len(self), len(point_names), len(self.coordinate_components)), self.coordinate_values, np.nan)
            self.confidence_values = self._grow((len(self), len(point_names)), self.confidence_values, 0.)
            self.point_names = point_names
            self.stage_indices = {stage: tuple(i for i, name in enumerate(point_names) if name.partition('.')[0] == stage)
                                  for stage in dict.fromkeys(name.partition('.')[0] for name in point_names)}
        box_shape = (len(self), len(paths), max(box_count, self.box_values.shape[2]), len(self.box_components))
        if box_shape != self.box_values.shape:
            self.box_values = self._grow(box_shape, self.box_values, np.nan)
        if paths != self.stage_paths:
            self.box_counts = self._grow((len(self), len(paths)), self.box_counts, 0)
            self.detector_values = self._grow((len(self), len(paths)), self.detector_values, False)
            self.stage_paths = paths
        if layout_index is None:
            self.stage_names = tuple(dict.fromkeys((*self.stage_names, *(stage.name for path, stage in stages if len(path) == 1))))
            layout_index = len(self.layouts)
            self.layouts.append(layout)
            self._layout_point_names.append(names)
            self._layout_lookup[layout] = layout_index
            self._layout_plans.append(tuple((self.stage_paths.index(path),
                None if stage.keypoints is None else point_selection(qualified_point_names(stage.name, stage.keypoints.names), point_names))
                for path, stage in stages))
        for (_, stage), (column, selection), boxes in zip(stages, self._layout_plans[layout_index], box_rows, strict=True):
            self.detector_values[index, column] = stage.detector_ran
            self.box_counts[index, column] = len(boxes)
            if len(boxes):
                self.box_values[index, column, :len(boxes)] = boxes
            if stage.keypoints is not None:
                points = stage.keypoints
                _, target = selection
                self.coordinate_values[index, target] = points.xyz
                self.confidence_values[index, target] = points.visibility
        self.timestamp_present[index] = observed_timestamp is not None
        if observed_timestamp is not None:
            self.observation_timestamps[index] = observed_timestamp
        self.layout_indices[index] = layout_index
        self.delivered[index] = True

    def finalize(self):
        """Restore chronological authored identity order once delivery is complete."""
        if self.finalized:
            return
        if not self.delivered.all():
            raise ValueError('Observation frame has not been delivered')
        indices, first = np.unique(self.layout_indices, return_index=True)
        ordered = indices[np.argsort(first)]
        names = tuple(dict.fromkeys(name for index in ordered for name in self._layout_point_names[index]))
        if names != self.point_names:
            from freemocap.core.tracking.observation_arrays import point_selection
            source, target = point_selection(self.point_names, names)
            permutation = source[np.argsort(target)]
            self.coordinate_values = self.coordinate_values.take(permutation, axis=1)
            self.confidence_values = self.confidence_values.take(permutation, axis=1)
            self.point_names = names
            self.stage_indices = {stage: tuple(i for i, name in enumerate(names) if name.partition('.')[0] == stage)
                                  for stage in dict.fromkeys(name.partition('.')[0] for name in names)}
        self.stage_names = tuple(dict.fromkeys(name for index in ordered for path, name, _ in self.layouts[index] if len(path) == 1))
        self.finalized = True

    def tracker_coordinates(self, selection=slice(None), *, point_indices=None):
        values = self.coordinate_values[selection]
        return values.copy() if point_indices is None else values[..., point_indices, :]

    def confidence_scores(self, selection=slice(None)):
        return self.confidence_values[selection]

    def require_stage(self, stage_name):
        authored_names = None
        for layout_index in np.unique(self.layout_indices):
            if layout_index < 0:
                raise ValueError('Observation frame has not been delivered')
            stage_names = next((names for _, name, names in self.layouts[layout_index] if name == stage_name), None)
            if stage_names is None:
                raise ValueError(f'Observation stage {stage_name!r} missing from a recording frame')
            if authored_names is not None and authored_names != stage_names:
                raise ValueError('Stage keypoint order changed within the recording')
            authored_names = stage_names

    def annotation_frame(self, index):
        from skellytracker.core.data_primitives.keypoints import Keypoints
        from skellytracker.core.data_primitives.observation import Observation, StageObservation
        from skellytracker.core.data_primitives.bounding_box import BoundingBox
        self[index]  # Require delivered coverage before constructing an adapter.
        roots, parents = {}, {}
        for path, name, names in self.layouts[self.layout_indices[index]]:
            column = self.stage_paths.index(path)
            indices = [self.point_names.index(f'{name}.{point}') for point in names] if names is not None else []
            stage = StageObservation(name=name, detector_ran=bool(self.detector_values[index, column]),
                bounding_boxes=[BoundingBox(*values) for values in self.box_values[index, column, :self.box_counts[index, column]]],
                keypoints=None if names is None else Keypoints(names=names,
                    xyz=self.coordinate_values[index, indices], visibility=self.confidence_values[index, indices]))
            (roots if len(path) == 1 else parents[path[:-1]].children)[path[-1]] = stage
            parents[path] = stage
        return Observation(frame_number=self.frame_numbers[index], image_size=self.image_size, stages=roots,
            timestamp=float(self.observation_timestamps[index]) if self.timestamp_present[index] else None)


@dataclass(frozen=True, slots=True)
class ObservationFrame:
    camera_series: ObservationSeries | RecordingObservationSeries
    sample_index: int

    @property
    def frame_number(self):
        return self.camera_series.frame_numbers[self.sample_index]

    @property
    def timestamp(self):
        if isinstance(self.camera_series, RecordingObservationSeries):
            return (float(self.camera_series.observation_timestamps[self.sample_index])
                    if self.camera_series.timestamp_present[self.sample_index] else None)
        return float(self.camera_series.timestamps_s[self.sample_index])

    @property
    def image_size(self):
        return self.camera_series.image_size


@dataclass(frozen=True)
class ObservationFrames(Sequence):
    """Camera maps contain views only; numerical storage stays in camera tensors."""
    camera_series: dict[str, ObservationSeries | RecordingObservationSeries]
    _final_names: tuple[str, ...] | None = field(default=None, init=False, repr=False)
    _final_stages: tuple[str, ...] | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if not self.camera_series:
            raise ValueError('Saved observations require cameras')
        frames = self.frame_numbers
        if any(series.frame_numbers != frames for series in self.camera_series.values()):
            raise ValueError('Saved camera observations disagree on frame numbers')

    @property
    def frame_numbers(self):
        return next(iter(self.camera_series.values())).frame_numbers

    @property
    def point_names(self):
        if self._final_names is not None:
            return self._final_names
        if all(isinstance(series, RecordingObservationSeries) for series in self.camera_series.values()):
            return self._chronological_identities()[0]
        return tuple(dict.fromkeys(name for series in self.camera_series.values() for name in series.point_names))

    @property
    def stage_names(self):
        if self._final_stages is not None:
            return self._final_stages
        if all(isinstance(series, RecordingObservationSeries) for series in self.camera_series.values()):
            return self._chronological_identities()[1]
        return tuple(dict.fromkeys(name for series in self.camera_series.values() for name in series.stage_names))

    def _chronological_identities(self):
        appearances = []
        for camera_index, series in enumerate(self.camera_series.values()):
            layout_indices, first = np.unique(series.layout_indices, return_index=True)
            appearances.extend((int(frame), camera_index, int(layout)) for frame, layout in zip(first, layout_indices, strict=True) if layout >= 0)
        ordered_series = tuple(self.camera_series.values())
        names, stages = {}, {}
        for _, camera, layout in sorted(appearances):
            series = ordered_series[camera]
            names.update(dict.fromkeys(series._layout_point_names[layout]))
            stages.update(dict.fromkeys(name for path, name, _ in series.layouts[layout] if len(path) == 1))
        return tuple(names), tuple(stages)

    def finalize(self):
        if self._final_names is not None:
            return
        if all(isinstance(series, RecordingObservationSeries) for series in self.camera_series.values()):
            for series in self.camera_series.values():
                series.finalize()
            names, stages = self._chronological_identities()
            object.__setattr__(self, '_final_names', names)
            object.__setattr__(self, '_final_stages', stages)

    def __len__(self):
        return len(next(iter(self.camera_series.values())))

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        return {camera: series[index] for camera, series in self.camera_series.items()}
