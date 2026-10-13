"""Resolve automatic board layout before constructing recording detector sessions."""
from collections.abc import Callable
from concurrent.futures import CancelledError
from contextlib import ExitStack

from skellycam.core.recorders.videos.sequential_video_reader import SequentialVideoReader
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardSelector

from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tracking.board_selection import CharucoBoardMode


def resolve_recording_board(*, sources: RecordingVideoSources, config: PosthocMocapPipelineConfig,
                            cancelled: Callable[[], bool], report: Callable[[str], None]) -> PosthocMocapPipelineConfig:
    if not config.charuco_tracking_enabled or config.board_mode == CharucoBoardMode.EXPLICIT:
        return config
    selector = CharucoBoardSelector()
    report('Detecting ChArUco board layout from recording videos')
    with ExitStack() as cleanup:
        readers = []
        for source in sources.camera_sources:
            if cancelled():
                raise CancelledError('Board detection cancelled')
            reader = SequentialVideoReader(path=source.video_metadata.file_path)
            cleanup.callback(reader.close)
            readers.append(reader)
        for number in range(sources.camera_sources[0].video_metadata.frame_count):
            if cancelled():
                raise CancelledError('Board detection cancelled')
            # The existing selector consumes this iterator only on its search frames.
            # Reader memory stays bounded, and tracking subsequently starts at frame zero.
            def images():
                for reader in readers:
                    if cancelled():
                        raise CancelledError('Board detection cancelled')
                    yield reader.read_bgr(frame_number=number)
            selected = selector.search_frame(frame_number=number, images=images())
            if selected is not None:
                selected = selected.model_copy(update={'square_length_mm': config.charuco_board.square_length_mm})
                report(f'Detected ChArUco board: {selected.squares_x} x {selected.squares_y}; square length {selected.square_length_mm:g} mm')
                return config.model_copy(update={'board_mode': CharucoBoardMode.EXPLICIT, 'charuco_board': selected})
    raise ValueError('Automatic board detection found no supported 5x3 or 7x5 board. Choose an explicit board for a custom layout, or disable board tracking if this recording has no board.')
