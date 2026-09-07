"""Sequential recording-group detection with one shared board selection."""

from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from skellytracker.core import Tracker, TrackerConfig
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
from skellytracker.core.detectors.keypoint_detectors.charuco.charuco_board_selection import CharucoBoardSelector
from skellytracker.core.tracker.tracker_state import TrackerState

from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper, VideoMetadata
from freemocap.core.tracking.tracker_factory import build_charuco_tracker, build_configured_tracker


@dataclass(frozen=True, slots=True)
class MocapDetectionRequest:
    recording_path: Path
    tracker_config: TrackerConfig
    detect_board: bool
    auto_select_board: bool
    board: CharucoBoardDefinition
    should_continue: Callable[[], bool]


@dataclass(frozen=True, slots=True)
class MocapDetectionFrame:
    frame_number: int
    frame_count: int
    images: dict[str, NDArray[np.uint8]]
    observations: dict[str, Observation]
    selected_board: CharucoBoardDefinition | None
    video_metadata: dict[str, VideoMetadata]


def detect_mocap_recording(request: MocapDetectionRequest) -> Iterator[MocapDetectionFrame]:
    """Yield complete multiframes; closing the iterator releases readers and trackers.

    Board search never skips human processing. Images are retained only for the current
    multiframe; consumers must finish encoding before advancing or retain their own copy.
    Cancellation returns without claiming that the recording is complete.
    """
    with ExitStack() as cleanup:
        group = VideoGroupHelper.from_recording_path(recording_path=str(request.recording_path))
        cleanup.callback(group.close)
        if not request.should_continue():
            return
        tracker = build_configured_tracker(config=request.tracker_config, batch_size=len(group.videos))
        cleanup.callback(tracker.close)
        states: dict[str, TrackerState] = {}
        board_states: dict[str, TrackerState] = {}
        board_tracker: Tracker | None = None
        selected_board = request.board if request.detect_board and not request.auto_select_board else None
        selector = CharucoBoardSelector() if request.detect_board and request.auto_select_board else None

        for frame_number in range(group.frame_count):
            if not request.should_continue():
                return
            images: dict[str, NDArray[np.uint8]] = {}
            for camera_id, video in group.videos.items():
                images[camera_id] = video.video_reader.read_bgr(frame_number=frame_number)
            observations, states = tracker.process_batch(images=images, frame_number=frame_number, states=states)
            if selector is not None and selected_board is None:
                detected_board = selector.search_frame(frame_number=frame_number, images=images.values())
                if detected_board is not None:
                    selected_board = detected_board.model_copy(update={"square_length_mm": request.board.square_length_mm})
            if selected_board is not None:
                if board_tracker is None:
                    board_tracker, _ = build_charuco_tracker(board_def=selected_board)
                    cleanup.callback(board_tracker.close)
                board_observations, board_states = board_tracker.process_batch(
                    images=images, frame_number=frame_number, states=board_states,
                )
                for camera_id, board_observation in board_observations.items():
                    observation = observations[camera_id]
                    if observation.stages.keys() & board_observation.stages.keys():
                        raise ValueError("Mocap and board trackers must have distinct stage names")
                    observation.stages.update(board_observation.stages)
            if not request.should_continue():
                return
            yield MocapDetectionFrame(
                frame_number=frame_number, frame_count=group.frame_count,
                images=images, observations=observations, selected_board=selected_board,
                video_metadata=group.video_metadata_by_id,
            )
        if request.should_continue():
            for video in group.videos.values():
                try:
                    video.video_reader.read_bgr(frame_number=group.frame_count)
                except IndexError:
                    continue
                raise ValueError(f"Video contains more than the declared {group.frame_count} frames: {video.video_path}")
