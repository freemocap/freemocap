"""Recorded source labels remain independent of calibration camera identifiers."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.reconstruction.posthoc_reconstruction import triangulate_observation_buffers
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingConfig, CameraMatchingStatus, MatchingFailurePolicy
from freemocap.core.tasks.calibration.camera_matching.posthoc_matching import PosthocMatchingRequest
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from freemocap.tests.calibration.test_matching_fitness import camera_rig, observations


def recorded_request() -> PosthocMatchingRequest:
    cameras = camera_rig()
    pixels = observations(cameras)[[2, 0, 1]]
    sources = ("renamed 9.mp4", "other.mov", "camera 12.avi")
    names = tuple(f"point {index}" for index in range(pixels.shape[2]))
    frames = [{
        source: Observation(frame_number=frame, image_size=(720, 1280), stages={
            "subject": StageObservation(name="subject", keypoints=Keypoints(
                names=names, xyz=np.column_stack((pixels[index, frame], np.zeros(len(names)))),
                visibility=np.ones(len(names)),
            )),
        }) for index, source in enumerate(sources)
    } for frame in range(pixels.shape[1])]
    videos = {source: VideoMetadata(
        file_path=Path(source), width=1280, height=720, fps=30.0,
        frame_count=len(frames), fourcc="test", duration_seconds=len(frames) / 30.0,
    ) for source in sources}
    return PosthocMatchingRequest(frames=frames, videos=videos, cameras=cameras, config=CameraMatchingConfig())


def test_recorded_matching_feeds_triangulation_without_relabeling_models() -> None:
    request = recorded_request()
    result = request.evaluate()
    assert result.status is CameraMatchingStatus.MATCHED
    geometry = request.resolve(result=result)
    assert tuple(camera.id for camera in geometry.values()) == ("camera 2", "camera 0", "camera 1")
    assert geometry["renamed 9.mp4"] is request.cameras[2]
    buffers = {source: ObservationBuffer() for source in request.videos}
    for frame in request.frames:
        for source, observation in frame.items():
            buffers[source].add_observation(observation)
    values, names, _ = triangulate_observation_buffers(
        observation_buffers=buffers, camera_geometry=geometry, triangulation_config=None,
        max_reprojection_error_px=None, timing=PosthocTimingReport(),
    )
    assert values.shape == (12, 10, 3)
    assert len(names) == 10 and np.isfinite(values).all()


def test_stop_policy_rejects_provisional_result_but_continue_retains_it() -> None:
    request = recorded_request()
    result = replace(request.evaluate(), status=CameraMatchingStatus.POOR)
    assert len(request.resolve(result=result)) == 3
    strict = replace(request, config=CameraMatchingConfig(failure_policy=MatchingFailurePolicy.STOP))
    with pytest.raises(ValueError, match="failure policy"):
        strict.resolve(result=result)
