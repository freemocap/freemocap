"""Restore canonical 2D detections without opening videos or creating detectors."""

from dataclasses import dataclass

from freemocap.core.tracking.observation_series import ObservationSeries, ObservationFrames
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
from skellycam.core.timestamps.recording_timing_reader import RecordingTiming, TimingMethod
from freemocap.core.reconstruction.recording_timing import RecordingGroupTiming

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@dataclass(frozen=True)
class SavedObservations:
    frames: ObservationFrames
    videos: dict[str, VideoMetadata]
    config: PosthocMocapPipelineConfig
    timing: RecordingGroupTiming

    @property
    def sensor_group(self) -> str:
        return next(iter(self.frames.camera_series.values())).channel_arrays.context.sensor_group


def read_saved_observations(*, structure: RecordingStructure, run_id: int,
                            sensor_group: str | None) -> SavedObservations:
    with recording_write_lock(structure=structure), recording_view(structure.data_parquet_path) as view:
        metadata = view.metadata
        if metadata.recording_id != structure.recording_name:
            raise ValueError('Recording identity does not match its directory')
        run = metadata.runs[run_id]
        from freemocap.core.pipeline.posthoc.saved_stage_processing import select_group
        sensor_group = select_group(run, sensor_group)
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
        camera_series = {}
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
                metadata=metadata, channel=channel, view=view)
            if frame_numbers is None:
                frame_numbers = points.frames
            elif frame_numbers != points.frames:
                raise ValueError('Saved camera observations disagree on frame numbers')
            camera_series[camera] = ObservationSeries(camera_id=camera,
                image_size=(image['height'], image['width']), channel_arrays=points.channel_arrays)
            fps = source['nominal_fps']
            camera_timing[camera] = RecordingTiming(timestamps_s=points.timestamps_s,
                method=TimingMethod(source['timing_method']))
            video_path = structure.videos_synchronized_dir / source['video_filename']
            # The application still records and imports synchronized_videos/.
            # Locate the saved camera filename without decoding it: numerical
            # restarts do not require images, but annotation needs the real path.
            flat_path = structure.full_path / 'synchronized_videos' / source['video_filename']
            if not video_path.is_file() and flat_path.is_file():
                video_path = flat_path
            videos[camera] = VideoMetadata(
                file_path=video_path,
                width=image['width'], height=image['height'], fps=fps,
                frame_count=points.frames[-1] + 1, start_frame=points.frames[0],
                end_frame=points.frames[-1] + 1, fourcc='', duration_seconds=(points.frames[-1] + 1) / fps,
            )
        timing_channels = [c for c in run.channels if c.sensor_group == sensor_group
                           and c.kind == ChannelKind.TIMESTAMPS and c.names == ('synchronized',)]
        if len(timing_channels) != 1:
            raise ValueError('Saved observations require synchronized group timing')
        timeline = read_saved_channel(structure=structure, run_id=run_id,
            metadata=metadata, channel=timing_channels[0], view=view)
        if timeline.frames != frame_numbers:
            raise ValueError('Saved timing and observations disagree on frame numbers')
        timing = RecordingGroupTiming(cameras=camera_timing, synchronized=RecordingTiming(
            timestamps_s=timeline.timestamps_s,
            method=TimingMethod(run.sources[timing_channels[0].source].definition['method'])))
        return SavedObservations(frames=ObservationFrames(camera_series), videos=videos, config=config, timing=timing)
