"""Resolve one recording's processing and publication timelines through SkellyCam."""

from dataclasses import dataclass
from pathlib import Path

from skellycam.core.timestamps.recording_timing_reader import (
    RecordingTiming, TimingFileKind, TimingMethod, read_recording_timing,
    recorded_camera_timing_path, recorded_multiframe_timing_path, resolve_camera_timing,
)

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata


@dataclass(frozen=True, slots=True)
class RecordingGroupTiming:
    cameras: dict[str, RecordingTiming]
    synchronized: RecordingTiming

    @classmethod
    def resolve(
        cls, *, recording_folder: Path, videos: dict[str, VideoMetadata], frame_numbers: tuple[int, ...],
    ) -> "RecordingGroupTiming":
        if not videos or not frame_numbers:
            raise ValueError("Recording timing requires videos and frames")
        cameras: dict[str, RecordingTiming] = {}
        for source, video in videos.items():
            if frame_numbers != tuple(range(video.start_frame, video.end_frame)):
                raise ValueError("Observations must cover the selected video frame range")
            timeline = resolve_camera_timing(
                path=recorded_camera_timing_path(recording_folder=recording_folder, camera_id=source),
                frame_count=video.frame_count, fps=video.fps, offset_s=0.0,
            )
            cameras[source] = RecordingTiming(
                timestamps_s=tuple(timeline.timestamps_s[frame] for frame in frame_numbers), method=timeline.method,
            )
        group_path = recorded_multiframe_timing_path(recording_folder=recording_folder)
        if group_path is not None:
            recorded = read_recording_timing(path=group_path, kind=TimingFileKind.MULTIFRAME)
            synchronized = RecordingTiming(
                timestamps_s=tuple(recorded[frame] for frame in frame_numbers), method=TimingMethod.RECORDED,
            )
        else:
            synchronized = RecordingTiming(
                timestamps_s=tuple(sum(camera.timestamps_s[index] for camera in cameras.values()) / len(cameras)
                                   for index in range(len(frame_numbers))),
                method=TimingMethod.MEAN_CAMERA_TIMES,
            )
        return cls(cameras=cameras, synchronized=synchronized)
