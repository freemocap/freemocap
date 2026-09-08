"""Resolve recorded observation sources onto unchanged calibration camera models."""

from dataclasses import dataclass

import numpy as np
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.tasks.calibration.camera_matching.matching_evaluation import match_camera_geometry
from freemocap.core.tasks.calibration.camera_matching.matching_models import (
    CameraMatchingConfig, CameraMatchingRequest, CameraMatchingResult, CameraMatchingStatus, MatchingFailurePolicy,
)
from freemocap.core.tasks.calibration.camera_matching.observation_sampling import MatchingSampleLayout, sample_recorded_observations
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


@dataclass(frozen=True, slots=True)
class PosthocMatchingRequest:
    frames: list[dict[str, Observation]]
    videos: dict[str, VideoMetadata]
    cameras: tuple[CameraModel, ...]
    config: CameraMatchingConfig

    def evaluate(self) -> CameraMatchingResult:
        if not self.frames:
            raise ValueError("Camera matching requires recorded observations")
        source_ids = tuple(self.videos)
        sample_count = min(len(self.frames), max(24, 2 * self.config.minimum_frames))
        frame_indices = np.linspace(0, len(self.frames) - 1, sample_count, dtype=int)
        sampled = [self.frames[index] for index in frame_indices]
        names = tuple(dict.fromkeys(
            name for frame in sampled for observation in frame.values()
            for name in observation.to_keypoints().names
        ))[:64]
        by_id = {camera.id: index for index, camera in enumerate(self.cameras)}
        initial = tuple(by_id[source] for source in source_ids) if all(source in by_id for source in source_ids) else None
        if not names:
            return CameraMatchingResult(status=CameraMatchingStatus.INSUFFICIENT, assignment=initial, fitness=None, search=None)
        layout = MatchingSampleLayout(
            source_ids=source_ids, point_names=names,
            image_sizes=tuple((video.width, video.height) for video in self.videos.values()),
        )
        pixels = sample_recorded_observations(layout=layout, frames=sampled, maximum_frames=max(2, sample_count))
        # A detector-local instance ordering cannot establish cross-view identity.
        for frame_index, frame in enumerate(sampled):
            if any(len(stage.bounding_boxes) > 1 for observation in frame.values() for stage in observation.stages.values()):
                pixels[:, frame_index] = np.nan
        return match_camera_geometry(request=CameraMatchingRequest(
            source_ids=source_ids, image_sizes=layout.image_sizes, cameras=self.cameras,
            pixels=pixels, initial_assignment=initial, config=self.config,
        ))

    def resolve(self, *, result: CameraMatchingResult) -> dict[str, CameraModel]:
        if result.assignment is None:
            raise ValueError(f"No camera assignment available for triangulation: {result.status}")
        if self.config.failure_policy is MatchingFailurePolicy.STOP and result.status not in (
            CameraMatchingStatus.INITIAL_ACCEPTED, CameraMatchingStatus.MATCHED, CameraMatchingStatus.DISABLED,
        ):
            raise ValueError(f"Camera matching stopped by configured failure policy: {result.status}")
        return {source: self.cameras[index] for source, index in zip(self.videos, result.assignment, strict=True)}
