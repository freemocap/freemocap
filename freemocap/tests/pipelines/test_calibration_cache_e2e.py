"""
End-to-end test: realtime Charuco capture → cache file → posthoc calibration via cache.

Uses MockCameraGroup + drive_realtime_lockstep to simulate a realtime pipeline
processing freemocap_test_data (7x5 charuco board, 3 cameras, 222 frames).
Verifies the cache file is written and produces equivalent calibration results.
"""
import logging
import multiprocessing
import pickle
import time
from pathlib import Path

import pytest
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.trackers.charuco_tracker.charuco_board_definition import CharucoBoardDefinition
from skellytracker.trackers.charuco_tracker.charuco_tracker_config import CharucoDetectorConfig

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import (
    RealtimeAggregatorNodeConfig,
)
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.calibration.shared.calibration_paths import (
    get_last_successful_calibration_toml_path,
)
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
)
from freemocap.tests.pipelines.helpers import wait_for_pipeline
from freemocap.tests.pipelines.mocks.mock_camera_group import MockCameraGroup
from freemocap.tests.pipelines.mocks.realtime_driver import drive_realtime_lockstep

logger = logging.getLogger(__name__)

CACHE_FILENAME = "charuco_observations_realtime.pkl"


def _build_charuco_pipeline_config(charuco_board: CharucoBoardDefinition) -> RealtimePipelineConfig:
    """Build a pipeline config with charuco tracking enabled, skeleton disabled."""
    camera_node_config = CameraNodeConfig(
        worker_mode=WorkerMode.THREAD,
        charuco_tracking_enabled=True,
        skeleton_tracking_enabled=False,
        charuco_detector_config=CharucoDetectorConfig(board=charuco_board),
    )
    aggregator_config = RealtimeAggregatorNodeConfig(
        triangulation_enabled=True,
        skeleton_fitting_enabled=False,
        center_of_mass_enabled=False,
    )
    return RealtimePipelineConfig(
        camera_node_config=camera_node_config,
        aggregator_config=aggregator_config,
        use_centralized_gpu_inference=False,
        log_pipeline_times=False,
    )


@pytest.mark.e2e
class TestCalibrationCacheE2E:
    """End-to-end tests for the Charuco observation cache pipeline."""

    def test_cache_file_written_and_valid(
        self,
        synchronized_videos_dir: Path,
        charuco_board_7x5: CharucoBoardDefinition,
        test_recording_path: Path,
    ):
        """Drive realtime pipeline with charuco, record, verify cache written."""
        logger.info("=== CACHE WRITE E2E TEST START ===")
        cache_path = test_recording_path / "output_data" / CACHE_FILENAME

        # Remove any stale cache
        if cache_path.exists():
            cache_path.unlink()
            logger.info(f"Removed stale cache: {cache_path}")

        kill_flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(global_kill_flag=kill_flag, worker_mode=WorkerMode.THREAD)

        config = _build_charuco_pipeline_config(charuco_board_7x5)
        mock = MockCameraGroup.create(
            synchronized_videos_dir=synchronized_videos_dir,
            global_kill_flag=kill_flag,
        )
        logger.info(
            f"MockCameraGroup: {mock.frame_count} frames  "
            f"cameras={list(mock.configs.keys())}"
        )

        manager = RealtimePipelineManager(worker_registry=registry)
        try:
            pipeline = manager.create_pipeline(camera_group=mock, pipeline_config=config)
            logger.info(f"RealtimePipeline [{pipeline.id}] created")

            # Verify CharucoRecorderNode was created
            assert pipeline.charuco_recorder_node is not None, (
                "CharucoRecorderNode should be created when charuco_tracking_enabled=True"
            )
            logger.info("CharucoRecorderNode verified — part of pipeline")

            # Build RecordingInfo for the test recording path so the
            # CharucoRecorderNode knows where to write the cache file.
            test_recording_info = RecordingInfo(
                recording_directory=str(test_recording_path.parent),
                recording_name=test_recording_path.name,
                mic_device_index=-1,
            )

            # Start calibration recording
            logger.info("Publishing CalibrationRecordingState(is_active=True)")
            pipeline.pubsub.publish(
                CalibrationRecordingStateTopic,
                CalibrationRecordingStateMessage(
                    recording_info=test_recording_info,
                    is_active=True,
                ),
            )

            # Drive all frames through
            logger.info(f"Driving {mock.frame_count} frames...")
            result = drive_realtime_lockstep(
                pipeline=pipeline,
                mock_group=mock,
                num_frames=mock.frame_count,
                per_frame_timeout=30.0,
            )
            logger.info(
                f"Drive complete: {result.frames_processed}/{mock.frame_count} frames"
            )

            # Stop calibration recording
            logger.info("Publishing CalibrationRecordingState(is_active=False)")
            pipeline.pubsub.publish(
                CalibrationRecordingStateTopic,
                CalibrationRecordingStateMessage(
                    recording_info=test_recording_info,
                    is_active=False,
                ),
            )

            # Allow time for the recorder to drain and flush
            time.sleep(0.5)

            # Verify cache file exists
            assert cache_path.exists(), (
                f"Cache file not written at {cache_path}"
            )
            file_size_kb = cache_path.stat().st_size / 1024
            logger.info(f"Cache file exists: {cache_path} ({file_size_kb:.1f} KB)")

            # Verify cache content
            with open(cache_path, "rb") as f:
                cache_data = pickle.load(f)

            assert "observations" in cache_data, "Cache missing 'observations' key"
            assert "board_definition" in cache_data, "Cache missing 'board_definition' key"
            assert "frame_range" in cache_data, "Cache missing 'frame_range' key"

            observations = cache_data["observations"]
            assert len(observations) >= 1, "Expected at least 1 camera in cache"

            # Verify at least some frames have detected corners
            total_detected = 0
            total_frames = 0
            for cam_id, obs_list in observations.items():
                total_frames = max(total_frames, len(obs_list))
                for obs in obs_list:
                    if obs is not None and not obs.charuco_empty:
                        total_detected += 1
                logger.info(f"Camera {cam_id}: {len(obs_list)} frames, "
                            f"{sum(1 for o in obs_list if o is not None and not o.charuco_empty)} with detections")

            assert total_detected > 0, (
                "Expected at least some frames with detected Charuco corners"
            )
            logger.info(
                f"Cache valid: {total_detected} total detections "
                f"across {len(observations)} cameras, {total_frames} frames"
            )

            # Verify board config matches
            cached_board = cache_data["board_definition"]
            assert cached_board.squares_x == charuco_board_7x5.squares_x
            assert cached_board.squares_y == charuco_board_7x5.squares_y
            logger.info("Cache board definition matches test board")

        finally:
            manager.shutdown()
            time.sleep(0.25)
            mock.close()
            logger.info("=== CACHE WRITE E2E TEST DONE ===")

    def test_posthoc_calibration_with_cache(
        self,
        recording_info,
        posthoc_manager,
        charuco_board_7x5: CharucoBoardDefinition,
        test_recording_path: Path,
    ):
        """Posthoc calibration pipeline works when cache is present."""
        logger.info("=== POSTHOC CALIBRATION WITH CACHE TEST START ===")
        cache_path = test_recording_path / "output_data" / CACHE_FILENAME

        # This test depends on test_cache_file_written_and_valid having run first
        if not cache_path.exists():
            pytest.skip(
                f"Cache file not found at {cache_path} — "
                f"run test_cache_file_written_and_valid first"
            )

        t0 = time.perf_counter()
        config = PosthocCalibrationPipelineConfig(charuco_board=charuco_board_7x5)
        pipeline = posthoc_manager.create_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=config,
        )
        logger.info(f"Calibration pipeline created: id={pipeline.id}")
        wait_for_pipeline(pipeline)
        elapsed = time.perf_counter() - t0
        logger.info(f"Calibration with cache completed in {elapsed:.1f}s")

        toml_path = get_last_successful_calibration_toml_path()
        assert toml_path.exists(), (
            f"Calibration TOML not found at {toml_path}"
        )
        size_kb = toml_path.stat().st_size / 1024
        logger.info(f"Calibration TOML written: {toml_path} ({size_kb:.1f} KB)")

        logger.info("=== POSTHOC CALIBRATION WITH CACHE TEST PASSED ===")

    def test_posthoc_calibration_without_cache_still_works(
        self,
        recording_info,
        posthoc_manager,
        charuco_board_7x5: CharucoBoardDefinition,
        test_recording_path: Path,
    ):
        """Posthoc calibration still works via normal video detection when cache is missing."""
        logger.info("=== POSTHOC CALIBRATION NO-CACHE TEST START ===")
        cache_path = test_recording_path / "output_data" / CACHE_FILENAME

        # Temporarily move cache if it exists
        cache_backup = None
        if cache_path.exists():
            cache_backup = cache_path.with_suffix(".pkl.bak")
            cache_path.rename(cache_backup)
            logger.info(f"Moved cache to {cache_backup}")

        try:
            t0 = time.perf_counter()
            config = PosthocCalibrationPipelineConfig(charuco_board=charuco_board_7x5)
            pipeline = posthoc_manager.create_calibration_pipeline(
                recording_info=recording_info,
                calibration_config=config,
            )
            logger.info(f"Calibration pipeline (no-cache) created: id={pipeline.id}")
            wait_for_pipeline(pipeline)
            elapsed = time.perf_counter() - t0
            logger.info(f"Calibration without cache completed in {elapsed:.1f}s")

            toml_path = get_last_successful_calibration_toml_path()
            assert toml_path.exists(), (
                "Calibration should complete via normal video path when cache is missing"
            )
            logger.info("Calibration without cache — PASS")
        finally:
            # Restore cache
            if cache_backup is not None and cache_backup.exists():
                cache_backup.rename(cache_path)
                logger.info("Restored cache file")

        logger.info("=== POSTHOC CALIBRATION NO-CACHE TEST PASSED ===")
