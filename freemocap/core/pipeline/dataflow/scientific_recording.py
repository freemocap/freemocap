"""Camera-joined triangulation and a completion-gated canonical recording sink.

The existing recording-wide camera matcher remains an explicit prerequisite.
No numerical solver, coordinate conversion or storage format is reimplemented.
This module is a backend scientific slice, not the general graph scheduler.
"""
from collections.abc import Iterable, Callable
from dataclasses import dataclass, field, asdict
from concurrent.futures import CancelledError
from copy import deepcopy
import hashlib
import pickle
from time import perf_counter

import numpy as np
from skellytracker.core.data_primitives.observation import Observation
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.dataflow.camera_join import CameraFrameJoin, ProducerOutcome
from freemocap.core.pipeline.dataflow.tracker_adapter import TrackedCameraFrame
from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources, VideoSourceFinished
from freemocap.core.reconstruction.posthoc_reconstruction import RecordingTriangulation, triangulate_observation_buffers
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.reconstruction.recording_timing import RecordingGroupTiming
from freemocap.core.recording.result_processing.observation_inputs import ObservationGroup, ObservationRecordingRequest
from freemocap.core.recording.result_processing.observation_inputs import TrackerRecordingDefinition, DetectorRecordingDefinition
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations
from freemocap.core.recording.result_processing.provenance import ProvenanceContext
from freemocap.core.recording.sample_encoding.spatial_points import SpatialReference, SpatialPointSeries, PointSeriesDefinition
from freemocap.core.tasks.calibration.camera_matching.posthoc_matching import PosthocMatchingRequest, require_processing_assignment
from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingConfig, CameraMatchingResult
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.triangulation.helpers.reprojection_diagnostics import ReprojectionDiagnostics, NamedReprojectionDiagnostics
from freemocap.core.tasks.triangulation.helpers.triangulation_result import TriangulationResult
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from freemocap.core.tracking.observation_arrays import observation_point_names
from freemocap.core.types.channel_kind import ChannelKind


def camera_assignment_metadata(result: CameraMatchingResult, geometry: dict[str, CameraModel]) -> dict:
    """Preserve warning evidence and its units at every recording sink."""
    return {
        "status": result.status.value,
        "source_to_calibration": {source: camera.id for source, camera in geometry.items()},
        "fitness": {"status": result.fitness.status.value, "mean_cost": result.fitness.mean_cost,
                    "cameras": [asdict(camera) for camera in result.fitness.cameras]} if result.fitness is not None else None,
        "error_units": "pixels_at_1000_pixel_image_diagonal",
    }


class ObservationCollection:
    """Validate delivery identity separately from successful producer completion."""
    def __init__(self, *, sources: RecordingVideoSources, execution_id: str):
        self.sources = sources
        self.cameras = tuple(source.camera_id for source in sources.camera_sources)
        self.frame_count = sources.camera_sources[0].video_metadata.frame_count
        self.join = CameraFrameJoin(execution=execution_id, sensor_group=sources.sensor_group,
                                    cameras=self.cameras, frames=range(self.frame_count))
        self.frames: list[dict[str, Observation]] = [{} for _ in range(self.frame_count)]
        self.outcomes: list[VideoSourceFinished] = []
        self._sources = {source.camera_id: source for source in sources.camera_sources}

    def accept(self, event: TrackedCameraFrame | VideoSourceFinished) -> int | None:
        if isinstance(event, VideoSourceFinished):
            if event.outcome == ProducerOutcome.SUCCEEDED and event.loaded_frames != self.frame_count:
                raise ValueError("Successful source must cover the full recording")
            self.join.finish(event.camera_id, event.outcome, execution=event.execution_id, sensor_group=event.sensor_group)
            self.outcomes.append(event)
            return None
        key = event.frame_key
        if key.camera not in self._sources or key.frame not in range(self.frame_count):
            raise ValueError("Undeclared observation camera/frame")
        source = self._sources[key.camera]
        if event.observation.frame_number != key.frame or event.observation.image_size != (
            source.video_metadata.height, source.video_metadata.width
        ):
            raise ValueError("Observation frame/image identity differs from its source")
        if event.timestamp_s != source.camera_timing.timestamps_s[key.frame]:
            raise ValueError("Observation timestamp differs from the declared camera timeline")
        observation_point_names(event.observation)  # Validates identity without assembling numerical arrays.
        ready = self.join.receive(key)
        self.frames[key.frame][key.camera] = deepcopy(event.observation)
        return key.frame if ready is not None else None

    def require_complete(self) -> None:
        if not self.join.complete:
            raise ValueError("Scientific save requires complete successful coverage from every declared camera")


def observation_buffers(frames: list[dict[str, Observation]], cameras: tuple[str, ...]) -> dict[str, ObservationBuffer]:
    buffers = {camera: ObservationBuffer() for camera in cameras}
    for frame in frames:
        for camera in cameras:
            buffers[camera].add_observation(frame[camera])
    return buffers


class FrameTriangulation:
    """Eager numerical operation after geometry and all declared camera inputs exist.

    One backend owner dispatches calls. A later producer failure invalidates saving
    the accumulated recording, not the already computed transient frame results.
    """
    def __init__(self, *, sources: RecordingVideoSources, execution_id: str,
                 camera_geometry: dict[str, CameraModel], point_names: tuple[str, ...],
                 triangulation_config: TriangulationConfig):
        self.observations = ObservationCollection(sources=sources, execution_id=execution_id)
        if len(self.observations.cameras) < 2 or set(camera_geometry) != set(self.observations.cameras):
            raise ValueError("Metric triangulation requires resolved geometry for every declared camera")
        if len({camera.id for camera in camera_geometry.values()}) != len(camera_geometry):
            raise ValueError("Camera geometry assignments must be unique")
        if not point_names or len(set(point_names)) != len(point_names):
            raise ValueError("Triangulation requires a unique declared point axis")
        self.camera_geometry = deepcopy(camera_geometry)
        self.point_names = tuple(point_names)
        self.config = triangulation_config.model_copy(deep=True)
        self.results: dict[int, RecordingTriangulation] = {}

    def accept(self, event: TrackedCameraFrame | VideoSourceFinished) -> RecordingTriangulation | None:
        if isinstance(event, TrackedCameraFrame) and not set(observation_point_names(event.observation)).issubset(self.point_names):
            raise ValueError("Observation contains points outside the declared triangulation axis")
        frame = self.observations.accept(event)
        if frame is None:
            return None
        result = triangulate_observation_buffers(
            observation_buffers=observation_buffers([self.observations.frames[frame]], self.observations.cameras),
            camera_geometry=self.camera_geometry, triangulation_config=self.config,
            max_reprojection_error_px=None, timing=PosthocTimingReport(), point_names=self.point_names,
        )
        self.results[frame] = result
        return result

    def completed_result(self) -> RecordingTriangulation:
        self.observations.require_complete()
        if set(self.results) != set(range(self.observations.frame_count)):
            raise ValueError("Scientific save requires every triangulation result")
        ordered = [self.results[frame] for frame in range(self.observations.frame_count)]
        first = ordered[0]
        if any((result.sources, result.keypoint_names, result.diagnostic_point_names) !=
               (first.sources, first.keypoint_names, first.diagnostic_point_names) for result in ordered):
            raise ValueError("Triangulation axes changed during the recording")
        diagnostics = [result.reconstruction.diagnostics for result in ordered]
        if any(item is None or item.units != diagnostics[0].units for item in diagnostics):
            raise ValueError("Missing or inconsistent triangulation diagnostics")
        combined = ReprojectionDiagnostics(**{
            name: np.concatenate([getattr(item, name) for item in diagnostics], axis=1)
            for name in ("errors", "observed", "reconstructed", "weights")
        }, units=diagnostics[0].units)
        return RecordingTriangulation(sources=first.sources, keypoint_names=first.keypoint_names,
            diagnostic_point_names=first.diagnostic_point_names, reconstruction=TriangulationResult(
                points_3d=np.concatenate([item.reconstruction.points_3d for item in ordered]),
                per_camera_weights=np.concatenate([item.reconstruction.per_camera_weights for item in ordered]),
                reprojection_error=np.concatenate([item.reconstruction.reprojection_error for item in ordered], axis=1),
                diagnostics=combined))


@dataclass(frozen=True)
class CompletedScientificRecording:
    observations: ObservationCollection
    triangulation: RecordingTriangulation
    camera_geometry: dict[str, CameraModel]
    matching_result: CameraMatchingResult
    matching_config: CameraMatchingConfig
    triangulation_config: TriangulationConfig
    execution_timing: PosthocTimingReport = field(default_factory=PosthocTimingReport, compare=False)
    _integrity_digest: bytes = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # Own the complete scientific payload, including mutable model/array data.
        for name in ("observations", "triangulation", "camera_geometry", "matching_result",
                     "matching_config", "triangulation_config"):
            object.__setattr__(self, name, deepcopy(getattr(self, name)))
        object.__setattr__(self, "_integrity_digest", self._payload_digest())

    def _payload_digest(self) -> bytes:
        # In-process mutation detection only: never persisted or deserialized.
        payload = (self.observations, self.triangulation, self.camera_geometry,
                   self.matching_result, self.matching_config, self.triangulation_config)
        return hashlib.sha256(pickle.dumps(payload, protocol=5)).digest()

    def save(self, *, recording_info: RecordingInfo, tracker_definition: TrackerRecordingDefinition,
             detector_definition: DetectorRecordingDefinition | None = None,
             models: tuple[RecordedModel, ...] = (), base_run_id: int = 0) -> RecordingMetadata:
        """Save 2D observations and raw 3D through the existing validated writer.

        Does not claim filtering, alignment or reconstruction completion.
        Destination/run selection remains explicit and uses normal writer semantics.
        """
        self.observations.require_complete()
        if self._payload_digest() != self._integrity_digest:
            raise ValueError("Scientific payload changed after computation")
        require_processing_assignment(result=self.matching_result, config=self.matching_config)
        sources = self.observations.sources
        result = self.triangulation
        if tracker_definition.point_names != result.diagnostic_point_names:
            raise ValueError("Saved tracker definition must match the measured point axis")
        tracker_definition = tracker_definition.model_copy(update={"configuration": {
            **tracker_definition.configuration, "camera_matching": self.matching_config.model_dump(mode="json"),
            "camera_assignment": camera_assignment_metadata(self.matching_result, self.camera_geometry),
            "triangulation_config": self.triangulation_config.model_dump(mode="json"),
        }})
        request = ObservationRecordingRequest(
            recording=recording_info, group=ObservationGroup(name=sources.sensor_group,
                frames=self.observations.frames,
                videos={source.camera_id: source.video_metadata for source in sources.camera_sources}),
            tracker=tracker_definition, detector=detector_definition, models=tuple(models),
            reconstructions=(), filtering=None, base_run_id=base_run_id,
            camera_geometry=tuple(self.camera_geometry[camera] for camera in self.observations.cameras),
            resolved_timing=RecordingGroupTiming(
                cameras={source.camera_id: source.camera_timing for source in sources.camera_sources},
                synchronized=sources.group_timing),
            spatial_series=(SpatialPointSeries(definition=PointSeriesDefinition(
                kind=ChannelKind.RAW_KEYPOINTS_3D, sensor_group=sources.sensor_group,
                source=tracker_definition.name, names=result.keypoint_names,
                reference=SpatialReference.for_camera_count(len(result.sources))), values=result.reconstruction.points_3d),),
            reprojection=NamedReprojectionDiagnostics(source_ids=result.sources,
                point_names=result.diagnostic_point_names, values=result.reconstruction.diagnostics),
            provenance_context=ProvenanceContext.create(),
        )
        return publish_posthoc_observations(request)


def process_resolved_scientific_recording(
    *, events: Iterable[TrackedCameraFrame | VideoSourceFinished], sources: RecordingVideoSources,
    execution_id: str, calibration_cameras: tuple[CameraModel, ...],
    matching_result: CameraMatchingResult, matching_config: CameraMatchingConfig,
    point_names: tuple[str, ...], triangulation_config: TriangulationConfig,
    cancelled: Callable[[], bool] = lambda: False,
) -> CompletedScientificRecording:
    """Consume ready camera frames immediately using an already resolved assignment.

    The backend owns consumption; this function never waits for a viewer. Assignment
    evidence and the declared point axis must belong to these recording inputs.
    Completion and scientific saving remain separate from per-frame readiness.
    """
    matching = PosthocMatchingRequest(frames=[],
        videos={source.camera_id: source.video_metadata for source in sources.camera_sources},
        cameras=calibration_cameras, config=matching_config)
    geometry = matching.resolve(result=matching_result)
    operation = FrameTriangulation(sources=sources, execution_id=execution_id,
        camera_geometry=geometry, point_names=point_names, triangulation_config=triangulation_config)
    for event in events:
        if cancelled():
            raise CancelledError("Scientific recording cancelled")
        operation.accept(event)
    if cancelled():
        raise CancelledError("Scientific recording cancelled")
    return CompletedScientificRecording(operation.observations, operation.completed_result(), operation.camera_geometry,
                                        matching_result, matching_config, operation.config)


def process_scientific_recording(*, events: Iterable[TrackedCameraFrame | VideoSourceFinished],
                                 sources: RecordingVideoSources, execution_id: str,
                                 calibration_cameras: tuple[CameraModel, ...], matching_config: CameraMatchingConfig,
                                 triangulation_config: TriangulationConfig,
                                 cancelled: Callable[[], bool] = lambda: False) -> CompletedScientificRecording:
    """Collect streaming observations, then use the recording-wide batch operation.

    Retains observations, never video images. Consume all healthy sources even when
    one source reports failure. Caller owns/ closes the event iterator on errors.
    """
    collection = ObservationCollection(sources=sources, execution_id=execution_id)
    for event in events:
        if cancelled():
            raise CancelledError("Scientific recording cancelled")
        collection.accept(event)
    return triangulate_completed_observations(collection=collection, calibration_cameras=calibration_cameras,
        matching_config=matching_config, triangulation_config=triangulation_config, cancelled=cancelled)


def triangulate_completed_observations(
    *, collection: ObservationCollection, calibration_cameras: tuple[CameraModel, ...],
    matching_config: CameraMatchingConfig, triangulation_config: TriangulationConfig,
    cancelled: Callable[[], bool] = lambda: False,
) -> CompletedScientificRecording:
    """Match and batch-triangulate available observations without replaying events.

    Only compact observations are retained; this never loads video images. The
    resolved streaming entry point remains separate from this recording operation.
    """
    collection.require_complete()
    if len(collection.cameras) < 2:
        raise ValueError("Metric triangulation requires at least two declared cameras")
    if cancelled():
        raise CancelledError("Scientific recording cancelled")
    sources = collection.sources
    timing = PosthocTimingReport()
    started = perf_counter()
    matching = PosthocMatchingRequest(frames=collection.frames,
        videos={source.camera_id: source.video_metadata for source in sources.camera_sources},
        cameras=tuple(calibration_cameras), config=matching_config)
    matching_result = matching.evaluate()
    geometry = matching.resolve(result=matching_result)
    if set(geometry) != set(collection.cameras) or len({camera.id for camera in geometry.values()}) != len(geometry):
        raise ValueError("Metric triangulation requires unique resolved geometry for every declared camera")
    timing.record("camera_assignment", perf_counter() - started)
    if cancelled():
        raise CancelledError("Scientific recording cancelled")
    started = perf_counter()
    buffers = observation_buffers(collection.frames, collection.cameras)
    names = tuple(dict.fromkeys(name for buffer in buffers.values() for name in buffer.keypoint_names))
    timing.record("observation_buffers", perf_counter() - started)
    started = perf_counter()
    result = triangulate_observation_buffers(observation_buffers=buffers, camera_geometry=geometry,
        triangulation_config=triangulation_config, max_reprojection_error_px=None,
        timing=timing, point_names=names)
    # The helper records solver/coordinate work; account for its array preparation too.
    helper_seconds = perf_counter() - started
    measured_seconds = sum(stage.elapsed_seconds for stage in timing.stages
                           if stage.name in ("triangulate", "reprojection_gate_and_blender"))
    timing.record("triangulation_array_preparation", max(0., helper_seconds - measured_seconds))
    if cancelled():
        raise CancelledError("Scientific recording cancelled")
    started = perf_counter()
    completed = CompletedScientificRecording(collection, result, geometry, matching_result,
        matching_config, triangulation_config, execution_timing=timing)
    timing.record("scientific_payload_snapshot", perf_counter() - started)
    return completed
