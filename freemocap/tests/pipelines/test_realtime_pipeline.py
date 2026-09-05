"""E2E: realtime pipeline driven by a mock camera group feeding the test videos."""
import logging
import multiprocessing
import time

import numpy as np
import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoDetectorConfig

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import (
    RealtimeAggregatorNodeConfig,
)
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.skeletons.standard_human_skeleton import STANDARD_HUMAN_MODEL_ID

from freemocap.tests.pipelines.mocks.mock_camera_group import MockCameraGroup
from freemocap.tests.pipelines.real_data_numeric_bounds import (
    COM_Z_MAX_MM,
    COM_Z_MIN_MM,
    PLAUSIBLE_BODY_HEIGHT_MM_RANGE,
)
from freemocap.tests.pipelines.mocks.realtime_driver import drive_realtime_lockstep

logger = logging.getLogger(__name__)


def _build_pipeline_config(mode: str, charuco_board) -> RealtimePipelineConfig:
    charuco_enabled = mode in ("charuco_only", "full")
    skeleton_enabled = mode == "full"
    logger.info(
        f"Building pipeline config: mode={mode!r}  "
        f"charuco={charuco_enabled}  skeleton={skeleton_enabled}"
    )
    camera_node_config = CameraNodeConfig(
        worker_mode=WorkerMode.THREAD,
        charuco_tracking_enabled=charuco_enabled,
        skeleton_tracking_enabled=skeleton_enabled,
        charuco_tracker_config=(
            TrackerConfig(
                stages=[
                    DetectionStageConfig(
                        name="charuco",
                        keypoint_detectors=[CharucoDetectorConfig(board=charuco_board)],
                    )
                ]
            )
            if charuco_enabled else None
        ),
    )
    aggregator_config = RealtimeAggregatorNodeConfig(
        triangulation_enabled=True,
        skeleton_fitting_enabled=skeleton_enabled,
        center_of_mass_enabled=skeleton_enabled,
    )
    return RealtimePipelineConfig(
        camera_node_config=camera_node_config,
        aggregator_config=aggregator_config,
        use_centralized_inference=True,
        log_pipeline_times=False,
    )


@pytest.mark.e2e
@pytest.mark.parametrize(
    "mode, per_frame_timeout",
    [
        ("charuco_only", 30.0),
        pytest.param("full", 120.0, marks=pytest.mark.slow),
    ],
)
def test_realtime_pipeline_processes_test_data(
    mode, per_frame_timeout, synchronized_videos_dir, charuco_board_7x5, calibration_toml_path,
):
    logger.info(
        f"=== REALTIME PIPELINE TEST: mode={mode!r}  "
        f"per_frame_timeout={per_frame_timeout}s ==="
    )
    logger.info(f"Videos dir: {synchronized_videos_dir}")
    logger.info(f"Calibration TOML: {calibration_toml_path}")

    kill_flag = multiprocessing.Value("b", False)
    registry = WorkerRegistry(global_kill_flag=kill_flag, worker_mode=WorkerMode.THREAD)

    config = _build_pipeline_config(mode, charuco_board_7x5)
    mock = MockCameraGroup.create(
        synchronized_videos_dir=synchronized_videos_dir,
        global_kill_flag=kill_flag,
    )
    logger.info(
        f"MockCameraGroup created: {mock.frame_count} frames  "
        f"cameras={list(mock.configs.keys())}"
    )

    manager = RealtimePipelineManager(worker_registry=registry)
    t0 = time.perf_counter()
    try:
        pipeline = manager.create_pipeline(camera_group=mock, pipeline_config=config)
        logger.info(f"Realtime pipeline created: id={pipeline.id}")

        result = drive_realtime_lockstep(
            pipeline=pipeline,
            mock_group=mock,
            num_frames=mock.frame_count,
            per_frame_timeout=per_frame_timeout,
        )
        elapsed = time.perf_counter() - t0
        fps = result.frames_processed / elapsed if elapsed > 0 else 0.0
        logger.info(
            f"Drive complete: {result.frames_processed}/{mock.frame_count} frames  "
            f"elapsed={elapsed:.1f}s  effective_fps={fps:.1f}"
        )

        frames_with_keypoints = sum(1 for o in result.outputs if len(o.keypoints_arrays) > 0)
        logger.info(
            f"Frames with 3D keypoints: {frames_with_keypoints}/{result.frames_processed}"
        )

        assert result.frames_processed >= int(0.9 * mock.frame_count), (
            f"Only processed {result.frames_processed}/{mock.frame_count} frames"
        )
        assert any(len(o.keypoints_arrays) > 0 for o in result.outputs), (
            "No frame produced triangulated 3D keypoints (calibration may not have loaded)"
        )

        if mode == "full":
            reconstructions = [
                o.reconstructions.get(STANDARD_HUMAN_MODEL_ID) for o in result.outputs
            ]
            skeletons = [r for r in reconstructions if r is not None]
            frames_with_skeleton = sum(1 for r in skeletons if r.segment_lengths)
            frames_with_com = sum(1 for r in skeletons if r.center_of_mass is not None)
            logger.info(
                f"Frames with fitted skeleton: {frames_with_skeleton}/{result.frames_processed}"
            )
            logger.info(
                f"Frames with center-of-mass: {frames_with_com}/{result.frames_processed}"
            )
            assert skeletons, "No fitted skeleton produced"
            assert any(r.center_of_mass is not None for r in skeletons), (
                "No center-of-mass result produced"
            )

            # Numerical sanity on the fitted skeleton (no semantic reading of the motion).
            for r in skeletons:
                if r.fitted_scale_mm is not None:
                    lo, hi = PLAUSIBLE_BODY_HEIGHT_MM_RANGE
                    assert lo < r.fitted_scale_mm < hi, (
                        f"fitted stature {r.fitted_scale_mm:.0f} mm outside {lo}-{hi} mm"
                    )
                for length in r.segment_lengths.values():
                    assert np.isfinite(length) and length > 0.0, (
                        f"non-positive/non-finite segment length {length}"
                    )
                if r.center_of_mass is not None:
                    assert COM_Z_MIN_MM <= r.center_of_mass[2] <= COM_Z_MAX_MM, (
                        f"CoM z {r.center_of_mass[2]:.0f} mm outside "
                        f"[{COM_Z_MIN_MM}, {COM_Z_MAX_MM}]"
                    )
                for name, q in r.segment_rotations_world.items():
                    assert abs(float(np.linalg.norm(q)) - 1.0) < 1e-3, (
                        f"non-unit quaternion for {name}"
                    )

        logger.info(f"=== REALTIME PIPELINE TEST PASSED: mode={mode!r} ===")
    finally:
        manager.shutdown()
        time.sleep(0.25)
        mock.close()
        logger.info("Realtime pipeline manager shut down and mock camera group closed")
