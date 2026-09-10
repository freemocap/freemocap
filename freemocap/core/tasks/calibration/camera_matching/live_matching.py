"""Pipeline-owned background matching with bounded observation storage."""

from concurrent.futures import Future, ThreadPoolExecutor
from collections.abc import Mapping
import logging

from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.tasks.calibration.camera_matching.matching_evaluation import match_camera_geometry
from freemocap.core.tasks.calibration.camera_matching.matching_lifecycle import MatchingAttempt, MatchingLifecycle, MatchingLifecycleState
from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingConfig, CameraMatchingRequest, CameraMatchingResult, CameraMatchingStatus
from freemocap.core.tasks.calibration.camera_matching.observation_sampling import MatchingSampleLayout, MatchingSampleWindow, select_matching_point_names
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker

logger = logging.getLogger(__name__)


class LiveGeometryMatcher:
    """One thread per aggregator; exceptions propagate through future.result()."""

    def __init__(self, *, calibration: CalibrationStateTracker, camera_indices: Mapping[str, int]) -> None:
        self._calibration = calibration
        self._camera_indices = dict(camera_indices)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="CameraGeometryMatching")
        self._lifecycle = MatchingLifecycle()
        self._window: MatchingSampleWindow | None = None
        self._future: Future[CameraMatchingResult] | None = None
        self._attempt: MatchingAttempt | None = None
        self._key: tuple[int, CameraMatchingConfig] | None = None

    def update(self, *, observations: dict[str, Observation], config: CameraMatchingConfig, elapsed_seconds: float) -> bool:
        key = (self._calibration.generation, config)
        if key != self._key:
            self._lifecycle.reset()
            self._window = None
            self._key = key
            self._calibration.reset_matching(camera_indices=self._camera_indices)
        changed = False
        if self._future is not None and self._future.done():
            result = self._future.result()
            if self._attempt is None:
                raise ValueError("Matching worker completed without an owned attempt")
            if self._lifecycle.finish(attempt=self._attempt, result=result):
                logger.info("Camera matching result: status=%s assignment=%s fitness=%s thresholds=%s", result.status, result.assignment, result.fitness, config.model_dump())
                self._calibration.apply_matching(source_ids=tuple(self._camera_indices), result=result, failure_policy=config.failure_policy)
                changed = result.assignment is not None and result.search is not None
            self._future = None
            self._attempt = None
        if (not config.automatically_match or self._calibration.calibration is None
                or self._lifecycle.state is MatchingLifecycleState.SUSPENDED
                or set(observations) != set(self._camera_indices) or len(observations) < 2):
            return changed
        if any(len(stage.bounding_boxes) > 1 for observation in observations.values() for stage in observation.stages.values()):
            return changed
        if self._window is None:
            names = select_matching_point_names(frames=[observations], minimum_visibility=config.minimum_point_visibility)
            if not names:
                return changed
            self._window = MatchingSampleWindow(
                layout=MatchingSampleLayout(
                    source_ids=tuple(self._camera_indices), point_names=names,
                    image_sizes=tuple(observations[source].image_size[::-1] for source in self._camera_indices),
                    minimum_visibility=config.minimum_point_visibility,
                ),
                capacity=max(24, config.minimum_frames * 2), interval_seconds=0.2,
            )
        if not self._window.append(observations=observations, elapsed_seconds=elapsed_seconds) or self._future is not None:
            return changed
        pixels = self._window.snapshot()
        if pixels.shape[1] < max(24, config.minimum_frames * 2):
            return changed
        cameras = tuple(self._calibration.calibration.cameras)
        if len(cameras) < len(self._camera_indices):
            result = CameraMatchingResult(status=CameraMatchingStatus.POOR, assignment=None, fitness=None, search=None)
            self._lifecycle.finish(attempt=self._lifecycle.begin(), result=result)
            self._calibration.apply_matching(source_ids=tuple(self._camera_indices), result=result, failure_policy=config.failure_policy)
            return True
        by_id = {camera.id: index for index, camera in enumerate(cameras)}
        binding = self._calibration.binding
        initial = tuple(by_id[binding.by_live_id[source].id] for source in self._camera_indices) if binding is not None and binding.applicable else None
        request = CameraMatchingRequest(
            source_ids=tuple(self._camera_indices), image_sizes=self._window.layout.image_sizes,
            cameras=cameras, pixels=pixels, initial_assignment=initial, config=config,
        )
        self._attempt = self._lifecycle.begin()
        logger.info("Camera matching sample: sources=%s cameras=%s initial_assignment=%s points=%s frames=%s", tuple(self._camera_indices), tuple(camera.id for camera in cameras), initial, self._window.layout.point_names, pixels.shape[1])
        self._future = self._executor.submit(match_camera_geometry, request=request)
        self._window.clear()
        return changed

    def close(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)
        if self._future is not None and not self._future.cancelled():
            self._future.result()
