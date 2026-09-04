"""CalibrationStateTracker: wraps calibration with validity tracking.

Uses Triangulator (pure CameraModel-based DLT) instead of AniposeCameraGroup.
Provides optimistic loading, graceful degradation on repeated triangulation
failure, and periodic file-change detection for hot-reloading.
"""

import logging
import os
import time
from collections.abc import Mapping
from pathlib import Path

from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer

import numpy as np
from numpy.typing import NDArray
from skellycam.core.types.type_overloads import CameraIdString, CameraIndexInt
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_paths import get_last_successful_calibration_toml_path
from freemocap.core.tasks.calibration.shared.calibration_camera_binding import (
    CalibrationBinding,
    CalibrationMatchKind,
    bind_calibration_to_live_cameras,
)
from freemocap.core.tasks.triangulation.helpers.angulation_result import AngulationResult
from freemocap.core.tasks.triangulation.helpers.project_single_camera import project_2d_observation_to_3d
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.triangulation.triangulator import Triangulator

logger = logging.getLogger(__name__)

# Invalidate calibration after this many consecutive triangulation failures
MAX_CONSECUTIVE_FAILURES: int = 10


def _strip_stage_prefix(name: str) -> str:
    """Strip the stage prefix that Observation.to_keypoints() adds.

    "body.nose" → "nose", "charuco.CharucoCorner-0" → "CharucoCorner-0".
    Names without a dot are returned unchanged.
    """
    dot = name.find(".")
    return name[dot + 1:] if dot != -1 else name


class CalibrationStateTracker:
    """Tracks whether we have a valid calibration and provides safe triangulation.

    Uses the pure Triangulator (DLT from CameraModel) rather than AniposeCameraGroup.

    Lifecycle:
      1. On creation, optimistically try to load the latest calibration.
      2. Triangulation requests go through try_triangulate(), which returns
         None if no valid calibration is loaded.
      3. If triangulation fails repeatedly (MAX_CONSECUTIVE_FAILURES), the
         calibration is invalidated. A single bad frame does not kill 3D.
      4. check_for_update() polls the calibration file mtime and reloads
         if the file has changed. Existing calibration is preserved if the
         file is unchanged or if loading the new file fails.
    """

    def __init__(self) -> None:
        self._calibration: CalibrationResult | None = None
        self._triangulator: Triangulator | None = None
        self._is_valid: bool = False
        self._consecutive_failure_count: int = 0
        self._calibration_path: Path | None = None
        self._calibration_file_mtime: float | None = None
        # Explicit calibration TOML to load from. None => use the canonical
        # most-recent calibration (and hot-reload that file).
        self._configured_path: Path | None = None
        # Maps frozenset of active calibration-name strings -> pre-built sub-Triangulator.
        # Lazily populated on first frame with a given camera subset; reused thereafter.
        self._subset_triangulator_cache: dict[frozenset, Triangulator] = {}
        # Which calibration camera describes which live camera, and whether the
        # calibration applies to this camera set at all. Recomputed only when the
        # calibration or the live camera set changes -- never per frame.
        self._binding: CalibrationBinding | None = None
        self._binding_key: tuple | None = None
        # The key we have already spoken about, so a persistent mismatch is reported
        # exactly once rather than on every frame.
        self._binding_reported_key: tuple | None = None
        # Bumped on every successful load. Part of the binding key so that reloading a
        # DIFFERENT calibration with the same camera set still re-evaluates.
        self._calibration_generation: int = 0

        # self._timer = PipelineStageTimer(name="CalibrationStateTracker")

    @classmethod
    def create_and_try_load(cls, calibration_toml_path: Path | None = None) -> "CalibrationStateTracker":
        """Create a tracker and optimistically try to load a calibration.

        Args:
            calibration_toml_path: Explicit calibration TOML to load from.
                If None, the canonical most-recent calibration is used.
        """
        tracker = cls()
        tracker._configured_path = calibration_toml_path
        tracker._try_load_latest()
        return tracker

    def set_source_path(self, calibration_toml_path: Path | None) -> bool:
        """Re-point the tracker at a different calibration source (live update).

        If the configured path changed, reloads immediately from the new
        source. None => fall back to the canonical most-recent calibration.

        Returns:
            True if a new calibration was loaded as a result.
        """
        if calibration_toml_path == self._configured_path:
            return False
        logger.info(
            f"Calibration source path changed: {self._configured_path} -> {calibration_toml_path}"
        )
        self._configured_path = calibration_toml_path
        return self._try_load_from_path(self._resolve_source_path())

    @property
    def is_valid(self) -> bool:
        return self._is_valid and self._triangulator is not None

    @property
    def binding(self) -> CalibrationBinding | None:
        """How the live cameras map onto the calibration, or None before `bind_live_cameras`."""
        return self._binding

    def is_applicable(self) -> bool:
        """Whether the loaded calibration actually describes the current camera set.

        Distinct from `is_valid`: a calibration can be perfectly well-formed and simply
        not describe the cameras that are plugged in right now. That is an expected
        condition, not a failure, and it must never discard the calibration.
        """
        return self.is_valid and self._binding is not None and self._binding.applicable

    def bind_live_cameras(
        self,
        *,
        live_camera_indices: Mapping[CameraIdString, CameraIndexInt],
    ) -> CalibrationBinding | None:
        """Resolve the live camera set against the loaded calibration.

        Cheap to call often: the answer is memoized on (calibration generation, live
        camera id+index set) and only recomputed when one of those changes. The result
        is reported exactly ONCE per key -- a calibration that does not fit the current
        cameras is normal, so it gets one WARNING and then silence, not a line per frame.

        Returns None when there is no calibration loaded at all.
        """
        if self._calibration is None:
            return None

        key = (
            self._calibration_generation,
            frozenset(live_camera_indices.items()),
        )
        if key == self._binding_key and self._binding is not None:
            return self._binding

        binding = bind_calibration_to_live_cameras(
            calibration_cameras=self._calibration.cameras,
            live_camera_indices=live_camera_indices,
        )
        self._binding = binding
        self._binding_key = key
        # A different binding means a different set of active cameras for the triangulator.
        self._subset_triangulator_cache.clear()

        if self._binding_reported_key != key:
            self._binding_reported_key = key
            if binding.kind is CalibrationMatchKind.EXACT:
                logger.info(f"Calibration applies to the live cameras. {binding.reason}")
            elif binding.kind is CalibrationMatchKind.INDEX:
                logger.warning(f"Calibration matched by index, not id. {binding.reason}")
            else:
                # Not an error. Cameras get replugged; the calibration on hand often
                # will not fit. Say it once, then run 2D-only until something changes.
                logger.warning(
                    f"Loaded calibration does not describe the connected cameras -- "
                    f"skipping triangulation (2D only) until the calibration or the "
                    f"camera set changes. {binding.reason}"
                )
        return binding

    @property
    def triangulator(self) -> Triangulator:
        """The loaded triangulator — raises when there is no valid calibration.

        Callers gate on ``is_valid`` first; this property fails loud rather
        than returning None for an unchecked caller.
        """
        if self._triangulator is None:
            raise ValueError("No valid calibration — triangulator is not available")
        return self._triangulator

    @property
    def calibration_path(self) -> Path | None:
        return self._calibration_path

    @property
    def calibration(self) -> CalibrationResult | None:
        """The loaded calibration, or None when there is no valid calibration."""
        return self._calibration

    def check_for_update(self) -> bool:
        """Check if the calibration file on disk has changed, and reload if so.

        Safe to call frequently (e.g. once per second). Does nothing if
        the file is unchanged or missing. Preserves existing calibration
        if the new file fails to load.

        Returns:
            True if a new calibration was loaded.
        """
        try:
            path = self._resolve_source_path()
            if not path.exists():
                return False
            mtime = os.path.getmtime(path)
            if mtime == self._calibration_file_mtime:
                return False
            logger.info(
                f"Calibration file changed on disk at {path} "
                f"(mtime={mtime}, previous_mtime={self._calibration_file_mtime})"
            )
            return self._try_load_from_path(path)
        except Exception as e:
            logger.debug(f"Error checking calibration file: {e}")
            return False

    def _resolve_source_path(self) -> Path:
        """The calibration file to load/poll: the explicitly configured TOML
        if set, else the canonical most-recent calibration."""
        return self._configured_path or get_last_successful_calibration_toml_path()

    def _try_load_latest(self) -> bool:
        """Try to load the calibration file from the configured/most-recent path.

        Returns:
            True if calibration was loaded successfully.
        """
        try:
            path = self._resolve_source_path()
            if path.exists():
                logger.info(f"Found calibration file at {path}")
                return self._try_load_from_path(path)
            else:
                logger.warning(
                    f"No calibration file found at {path}. "
                    f"Triangulation will be disabled until a calibration TOML is present at this path."
                )
                return False
        except Exception as e:
            logger.debug(f"No existing calibration found: {e}")
            return False

    def _try_load_from_path(self, path: Path) -> bool:
        """Attempt to load calibration from an anipose-format TOML file.

        On success, replaces the current calibration state.
        On failure, logs the error and leaves the existing state untouched.

        Returns:
            True if calibration was loaded successfully.
        """
        try:
            calibration = CalibrationResult.load_anipose_toml(path)
            cameras = calibration.cameras
            triangulator = Triangulator(cameras=cameras)

            # Only swap state after everything succeeded
            self._triangulator = triangulator
            self._calibration = calibration
            self._calibration_path = path
            self._is_valid = True
            self._consecutive_failure_count = 0
            self._calibration_file_mtime = os.path.getmtime(path)
            logger.info(
                f"Loaded calibration from {path} with "
                f"{len(cameras)} cameras: {[c.id for c in cameras]}"
            )
            self._calibration_generation += 1
            self._subset_triangulator_cache.clear()
            self._binding = None
            self._binding_key = None

            return True
        except Exception as e:
            logger.warning(f"Failed to load calibration from {path}: {e}", exc_info=True)
            return False

    def try_angulate(
        self,
        *,
        frame_number: int,
        frame_observations_by_camera: dict[CameraIdString, Observation],
        max_reprojection_error_px: float,
        triangulation_config: TriangulationConfig | None = None,
    ) -> AngulationResult | None:
        """Attempt triangulation with reprojection error gating.

        Uses to_keypoints() to get named 2D observations from each camera,
        finds points visible in ≥2 cameras, triangulates via DLT, and rejects
        points whose mean reprojection error exceeds max_reprojection_error_px.

        Returns an ``AngulationResult`` — triangulated 3D points plus their
        per-point mean reprojection errors (None on the single-camera planar
        path, where reprojection error is undefined) — or None if no valid
        calibration is loaded or triangulation failed.
        """
        if not self.is_valid:
            # Single-camera: projection doesn't need calibration
            if len(frame_observations_by_camera) == 1:
                obs = next(iter(frame_observations_by_camera.values()))
                self._consecutive_failure_count = 0
                return AngulationResult(
                    points=project_2d_observation_to_3d(observation=obs),
                    errors_px=None,
                )
            return None

        # Identity is settled before we get here, by `bind_live_cameras`. A calibration
        # that does not describe these cameras is an expected condition, already reported
        # once -- it is not a triangulation failure and must not touch the failure counter.
        if not self.is_applicable():
            return None

        if triangulation_config is None:
            triangulation_config = TriangulationConfig()

        try:
            binding = self._binding
            assert binding is not None  # guaranteed by is_applicable()

            # Map live cam_id -> calibration camera. The Triangulator is built from
            # calibration CameraModels, so its keys are calibration ids.
            matched_obs_by_cam: dict[str, Observation] = {}
            for cam_id, obs in frame_observations_by_camera.items():
                camera_model = binding.by_live_id.get(cam_id)
                if camera_model is None:
                    # A camera the binding does not cover (it appeared after the last
                    # bind). Skip its observation; the next bind will pick it up.
                    continue
                matched_obs_by_cam[camera_model.id] = obs

            if len(matched_obs_by_cam) == 0:
                return AngulationResult(points={}, errors_px={})
            if len(matched_obs_by_cam) == 1:
                obs = next(iter(matched_obs_by_cam.values()))
                result = project_2d_observation_to_3d(observation=obs)
                self._consecutive_failure_count = 0
                return AngulationResult(points=result, errors_px=None)

            # Reuse a cached sub-triangulator for this camera subset; only build
            # a new one when we see a novel active-camera combination.
            active_cam_set: frozenset[str] = frozenset(matched_obs_by_cam.keys())
            if active_cam_set == frozenset(self._triangulator.camera_ids):
                sub_triangulator = self._triangulator
            elif active_cam_set in self._subset_triangulator_cache:
                sub_triangulator = self._subset_triangulator_cache[active_cam_set]
            else:
                sub_triangulator = Triangulator(
                    cameras=[
                        cam for cam in self._triangulator.cameras
                        if cam.id in matched_obs_by_cam
                    ]
                )
                self._subset_triangulator_cache[active_cam_set] = sub_triangulator
            ordered_cam_names: list[str] = sub_triangulator.camera_ids
            n_cameras = len(ordered_cam_names)

            # All observations are now the same Observation type; use to_keypoints()
            # uniformly. Stack (n_cameras, n_points, 2) then filter to ≥2-camera points.
            ordered_obs: list[Observation] = [
                matched_obs_by_cam[c] for c in ordered_cam_names
            ]
            first_kpts = ordered_obs[0].to_keypoints()
            canonical_names: tuple[str, ...] = first_kpts.names

            _t0 = time.perf_counter()
            stacked = np.stack(
                [np.ascontiguousarray(obs.to_keypoints().xyz[:, :2], dtype=np.float64)
                 for obs in ordered_obs]
            )
            point_names_seq: tuple[str, ...] = canonical_names
            # Filter to points visible in ≥2 cameras
            visible_per_point = (~np.isnan(stacked[..., 0])).sum(axis=0)
            keep_mask = visible_per_point >= 2
            if not bool(keep_mask.any()):
                return AngulationResult(points={}, errors_px={})
            if not bool(keep_mask.all()):
                stacked = stacked[:, keep_mask, :]
                point_names_seq = tuple(
                    n for n, k in zip(canonical_names, keep_mask.tolist()) if k
                )
            # self._timer.record("build_stacked", (time.perf_counter() - _t0) * 1e3)

            # Triangulate the single frame
            _t0 = time.perf_counter()
            triangulation_result = sub_triangulator.triangulate(
                data2d=stacked,
                config=triangulation_config,
            )
            points_3d = triangulation_result.points_3d  # (n_points, 3)
#             self._timer.record("triangulate", (time.perf_counter() - _t0) * 1e3)

            # Reprojection error gate (in pixels, mean across valid cameras)
            _t0 = time.perf_counter()
            mean_reproj_error = sub_triangulator.mean_reprojection_error(
                points_3d=points_3d,
                points_2d_pixel=stacked,
            )  # (n_points,)
            bad_mask = mean_reproj_error > max_reprojection_error_px
            if np.any(bad_mask):
                n_bad = int(np.sum(bad_mask))
                n_total = len(point_names_seq)
                points_3d[bad_mask] = np.nan
#             self._timer.record("mean_reproj_error", (time.perf_counter() - _t0) * 1e3)

            # Build result, excluding NaN points. Strip the stage prefix that
            # to_keypoints() adds (e.g. "body.nose" → "nose") so downstream code
            # sees the canonical unprefixed names. Each surviving point keeps
            # its mean reprojection error alongside its position.
            _t0 = time.perf_counter()
            valid_pt_mask = ~np.isnan(points_3d).any(axis=1)
            points: dict[str, NDArray[np.float64]] = {}
            errors_px: dict[str, float] = {}
            for i, name in enumerate(point_names_seq):
                if valid_pt_mask[i]:
                    stripped = _strip_stage_prefix(name)
                    points[stripped] = points_3d[i]
                    errors_px[stripped] = float(mean_reproj_error[i])
#             self._timer.record("result_dict", (time.perf_counter() - _t0) * 1e3)
#             self._timer.maybe_report()

            # Triangulation succeeded — reset failure counter
            self._consecutive_failure_count = 0
            return AngulationResult(points=points, errors_px=errors_px)

        except (ValueError, IndexError, np.linalg.LinAlgError) as e:
            # NUMERICAL failure only. Camera-identity mismatch is settled up front by
            # `bind_live_cameras` and can no longer reach this counter; anything else
            # (a TypeError, an AttributeError) is a programming error and must escape.
            self._consecutive_failure_count += 1
            if self._consecutive_failure_count >= MAX_CONSECUTIVE_FAILURES:
                logger.error(
                    f"Triangulation failed numerically {self._consecutive_failure_count} times "
                    f"consecutively — invalidating calibration. Last error: {e}"
                )
                self._invalidate()
            else:
                logger.debug(
                    f"Triangulation failed (failure "
                    f"{self._consecutive_failure_count}/{MAX_CONSECUTIVE_FAILURES}): {e}",
                )
            return None

    def _invalidate(self) -> None:
        self._is_valid = False
        self._triangulator = None
        self._calibration = None
        self._calibration_path = None
        self._subset_triangulator_cache.clear()
        self._binding = None
        self._binding_key = None
        self._binding_reported_key = None
        # Preserve _calibration_file_mtime so we can detect when the file changes
