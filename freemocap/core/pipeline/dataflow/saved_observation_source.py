"""Restore the graph's observation source without opening videos or detectors."""
from pathlib import Path

from freemocap.core.pipeline.dataflow.scientific_recording import ObservationCollection
from freemocap.core.pipeline.dataflow.video_sources import CameraVideoSource, RecordingVideoSources
from freemocap.core.pipeline.posthoc.saved_stage_processing import recording_structure
from freemocap.core.recording.result_processing.saved_observations import read_saved_observations
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


def load_saved_observation_source(*, path: str, config: PosthocMocapPipelineConfig):
    structure = recording_structure(path)
    saved = read_saved_observations(structure=structure, run_id=config.base_run_id, sensor_group=config.sensor_group)
    group = saved.sensor_group
    sources = RecordingVideoSources(Path(path).resolve(), group, tuple(
        CameraVideoSource(camera, video, saved.timing.cameras[camera])
        for camera, video in saved.videos.items()), saved.timing.synchronized, saved_frame_numbers=saved.frames.frame_numbers)
    collection = ObservationCollection.from_saved(sources=sources, frames=saved.frames)
    collection.require_complete()
    # New tracker options do not relabel saved predictions from another model.
    detector_fields = {'detector_type', 'tracker_config', 'charuco_tracking_enabled', 'board_mode', 'charuco_board'}
    detector_fields.update(name for name in type(config).model_fields
        if name.startswith(('mediapipe_', 'rtmpose_')))
    effective = config.model_copy(update={name: getattr(saved.config, name) for name in detector_fields})
    return sources, collection, effective
