"""Restore canonical 2D detections without opening videos or creating detectors."""

from dataclasses import dataclass

import numpy as np
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
from skellycam.core.timestamps.recording_timing_reader import RecordingTiming, TimingMethod
from freemocap.core.reconstruction.recording_timing import RecordingGroupTiming

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@dataclass(frozen=True)
class SavedObservations:
    frames: list[dict[str, Observation]]
    videos: dict[str, VideoMetadata]
    config: PosthocMocapPipelineConfig
    timing: RecordingGroupTiming


def read_saved_observations(*, structure: RecordingStructure, run_id: int,
                            sensor_group: str) -> SavedObservations:
    with recording_write_lock(structure=structure):
        metadata = read_metadata(path=structure.data_parquet_path)
        if metadata.recording_id != structure.recording_name:
            raise ValueError('Recording identity does not match its directory')
        run = metadata.runs[run_id]
        channels = [c for c in run.channels if c.sensor_group == sensor_group
                    and c.kind == ChannelKind.OVERLAY_2D]
        if not channels or len({c.source for c in channels}) != 1:
            raise ValueError('Select a recording group with one saved keypoint tracker')
        configuration = dict(run.sources[channels[0].source].definition)
        # Older publications included Pydantic computed fields, which aren't inputs.
        configuration.pop('tracker_config', None)
        if isinstance(configuration.get('charuco_board'), dict):
            configuration['charuco_board'] = {name: value for name, value in configuration['charuco_board'].items()
                if name in CharucoBoardDefinition.model_fields}
        config = PosthocMocapPipelineConfig.model_validate(configuration)
        frames = None
        frame_numbers = None
        videos = {}
        camera_timing = {}
        for channel in channels:
            image = run.reference_frames[channel.reference_frame]
            camera = image['camera_id']
            if camera in videos:
                raise ValueError('Multiple observation channels for the same camera')
            source = run.sources[f'camera:{camera}'].definition
            points = read_saved_channel(structure=structure, run_id=run_id,
                metadata=metadata, channel=channel)
            if frames is None:
                frame_numbers = points.frames
                frames = [{} for _ in frame_numbers]
            elif frame_numbers != points.frames:
                raise ValueError('Saved camera observations disagree on frame numbers')
            if points.frames != tuple(range(points.frames[0], points.frames[-1] + 1)):
                raise ValueError('Saved observations must cover consecutive video frames')
            fps = source['nominal_fps']
            camera_timing[camera] = RecordingTiming(timestamps_s=points.timestamps_s,
                method=TimingMethod(source['timing_method']))
            videos[camera] = VideoMetadata(
                file_path=structure.videos_synchronized_dir / source['video_filename'],
                width=image['width'], height=image['height'], fps=fps,
                frame_count=points.frames[-1] + 1, start_frame=points.frames[0],
                end_frame=points.frames[-1] + 1, fourcc='', duration_seconds=(points.frames[-1] + 1) / fps,
            )
            components = list(channel.components)
            stages = {}
            for index, name in enumerate(channel.names):
                stage, separator, point = name.partition('.')
                if not separator:
                    raise ValueError('Saved observation name has no detector stage')
                stages.setdefault(stage, []).append((index, point))
            for index, number in enumerate(points.frames):
                observation = Observation(frame_number=number, image_size=(image['height'], image['width']),
                    timestamp=points.timestamps_s[index])
                for stage, entries in stages.items():
                    indices = [entry[0] for entry in entries]
                    xyz = np.zeros((len(indices), 3))
                    xyz[:, :2] = points.values[index, indices][:, [components.index('x'), components.index('y')]]
                    observation.stages[stage] = StageObservation(name=stage,
                        keypoints=Keypoints(names=tuple(entry[1] for entry in entries), xyz=xyz,
                            visibility=points.values[index, indices, components.index('visibility')].copy()))
                frames[index][camera] = observation
        timing_channels = [c for c in run.channels if c.sensor_group == sensor_group
                           and c.kind == ChannelKind.TIMESTAMPS and c.names == ('synchronized',)]
        if len(timing_channels) != 1:
            raise ValueError('Saved observations require synchronized group timing')
        timeline = read_saved_channel(structure=structure, run_id=run_id,
            metadata=metadata, channel=timing_channels[0])
        if timeline.frames != frame_numbers:
            raise ValueError('Saved timing and observations disagree on frame numbers')
        timing = RecordingGroupTiming(cameras=camera_timing, synchronized=RecordingTiming(
            timestamps_s=timeline.timestamps_s,
            method=TimingMethod(run.sources[timing_channels[0].source].definition['method'])))
        return SavedObservations(frames=frames, videos=videos, config=config, timing=timing)
