"""Restore the graph's observation source without opening videos or detectors."""
from pathlib import Path

from freemocap.core.pipeline.dataflow.camera_join import CameraFrameKey, ProducerOutcome
from freemocap.core.pipeline.dataflow.scientific_recording import ObservationCollection
from freemocap.core.pipeline.dataflow.tracker_adapter import TrackedCameraFrame
from freemocap.core.pipeline.dataflow.video_sources import CameraVideoSource, RecordingVideoSources, VideoSourceFinished
from freemocap.core.pipeline.posthoc.saved_stage_processing import recording_structure, select_group
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.result_processing.saved_observations import read_saved_observations
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


def load_saved_observation_source(*, path: str, config: PosthocMocapPipelineConfig):
    structure = recording_structure(path)
    metadata = read_metadata(path=structure.data_parquet_path)
    group = select_group(metadata.runs[config.base_run_id], config.sensor_group)
    saved = read_saved_observations(structure=structure, run_id=config.base_run_id, sensor_group=group)
    sources = RecordingVideoSources(Path(path).resolve(), group, tuple(
        CameraVideoSource(camera, video, saved.timing.cameras[camera])
        for camera, video in saved.videos.items()), saved.timing.synchronized)
    collection = ObservationCollection(sources=sources, execution_id='saved-observations')
    for source in sources.camera_sources:
        for index, frame in enumerate(saved.frames):
            collection.accept(TrackedCameraFrame(
                frame_key=CameraFrameKey(execution='saved-observations', sensor_group=group,
                    camera=source.camera_id, frame=index),
                timestamp_s=source.camera_timing.timestamps_s[index], observation=frame[source.camera_id]))
        collection.accept(VideoSourceFinished(execution_id='saved-observations', sensor_group=group,
            camera_id=source.camera_id, outcome=ProducerOutcome.SUCCEEDED, loaded_frames=len(saved.frames), error_message=None))
    collection.require_complete()
    # New tracker options do not relabel measurements already made by another model.
    detector_fields = {'detector_type', 'tracker_config', 'charuco_tracking_enabled', 'board_mode', 'charuco_board'}
    detector_fields.update(name for name in type(config).model_fields
        if name.startswith(('mediapipe_', 'rtmpose_')))
    effective = config.model_copy(update={name: getattr(saved.config, name) for name in detector_fields})
    return sources, collection, effective
