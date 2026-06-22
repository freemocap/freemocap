"""E2E: realtime pipeline driven by a mock camera group feeding the test videos."""
import logging
import multiprocessing
import time

import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.trackers.charuco_tracker.charuco_tracker_config import CharucoDetectorConfig

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import (
    RealtimeAggregatorNodeConfig,
)
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager

from freemocap.core.kinematics.segment_lengths import (
    build_segment_length_report,
    equivalence_violations,
)
from freemocap.tests.pipelines.anthropometry import positions_from_aggregation_outputs
from freemocap.tests.pipelines.mocks.mock_camera_group import MockCameraGroup
from freemocap.tests.pipelines.mocks.realtime_driver import drive_realtime_lockstep

logger = logging.getLogger(__name__)


def _assert_realtime_human_shaped_and_matches_posthoc(outputs, request) -> None:
    logger.info("Building segment-length report from raw realtime triangulation output...")
    realtime_report = build_segment_length_report(
        positions_from_aggregation_outputs(outputs)
    )
    logger.info("[realtime] " + realtime_report.summary())

    shape_violations = realtime_report.human_shape_violations(check_rigidity=False)
    if shape_violations:
        logger.warning(f"Realtime human-shape violations ({len(shape_violations)}):")
        for v in shape_violations:
            logger.warning(f"  FAIL: {v}")
    else:
        logger.info("Realtime raw reconstruction is human-shaped — PASS")

    assert not shape_violations, (
        "Realtime raw reconstruction is not human-shaped:\n  - "
        + "\n  - ".join(shape_violations) + "\n" + realtime_report.summary()
    )

    posthoc_report = request.getfixturevalue("posthoc_segment_report")
    logger.info("Checking realtime vs posthoc segment equivalence (threshold=25%)...")
    eq_violations = equivalence_violations(
        realtime_report, posthoc_report, label_a="realtime", label_b="posthoc",
    )

    assessable_rt = realtime_report.assessable()
    assessable_ph = posthoc_report.assessable()
    for name in sorted(set(assessable_rt) & set(assessable_ph)):
        rt_mm = assessable_rt[name].median_mm
        ph_mm = assessable_ph[name].median_mm
        diff_pct = abs(rt_mm - ph_mm) / ph_mm * 100 if ph_mm > 0 else float("inf")
        logger.info(
            f"  {name}: realtime={rt_mm:.0f}mm  posthoc={ph_mm:.0f}mm  diff={diff_pct:.1f}%"
        )

    if eq_violations:
        logger.warning(f"Realtime/posthoc equivalence violations ({len(eq_violations)}):")
        for v in eq_violations:
            logger.warning(f"  FAIL: {v}")
    else:
        logger.info("Realtime segment lengths match posthoc within 25% — PASS")

    assert not eq_violations, (
        "Realtime segment lengths differ from posthoc:\n  - "
        + "\n  - ".join(eq_violations)
        + "\n[realtime] " + realtime_report.summary()
        + "\n[posthoc]  " + posthoc_report.summary()
    )


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
        charuco_detector_config=(
            CharucoDetectorConfig(board=charuco_board) if charuco_enabled else None
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
        use_centralized_gpu_inference=False,
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
    request,
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
            frames_with_skeleton = sum(1 for o in result.outputs if o.skeleton)
            frames_with_com = sum(1 for o in result.outputs if o.center_of_mass_result is not None)
            logger.info(
                f"Frames with fitted skeleton: {frames_with_skeleton}/{result.frames_processed}"
            )
            logger.info(
                f"Frames with center-of-mass: {frames_with_com}/{result.frames_processed}"
            )
            assert any(o.skeleton for o in result.outputs), "No fitted skeleton produced"
            assert any(o.center_of_mass_result is not None for o in result.outputs), (
                "No center-of-mass result produced"
            )
            _assert_realtime_human_shaped_and_matches_posthoc(result.outputs, request)

        logger.info(f"=== REALTIME PIPELINE TEST PASSED: mode={mode!r} ===")
    finally:
        manager.shutdown()
        time.sleep(0.25)
        mock.close()
        logger.info("Realtime pipeline manager shut down and mock camera group closed")


@pytest.mark.e2e
@pytest.mark.slow
def test_realtime_pipeline_on_sample_data(
    sample_synchronized_videos_dir, charuco_board_7x5, calibration_toml_path,
    realtime_max_frames,
):
    """Exercise the realtime pipeline over the longer (non-downsampled) sample recording."""
    logger.info(
        f"=== REALTIME SAMPLE-DATA TEST ===  "
        f"max_frames={realtime_max_frames} (0=all)"
    )
    logger.info(f"Sample videos dir: {sample_synchronized_videos_dir}")

    kill_flag = multiprocessing.Value("b", False)
    registry = WorkerRegistry(global_kill_flag=kill_flag, worker_mode=WorkerMode.THREAD)

    config = _build_pipeline_config("full", charuco_board_7x5)
    mock = MockCameraGroup.create(
        synchronized_videos_dir=sample_synchronized_videos_dir,
        global_kill_flag=kill_flag,
    )
    n_frames = (
        mock.frame_count
        if realtime_max_frames <= 0
        else min(mock.frame_count, realtime_max_frames)
    )
    logger.info(
        f"MockCameraGroup: {mock.frame_count} total frames  "
        f"cameras={list(mock.configs.keys())}  "
        f"driving {n_frames} frames"
    )

    manager = RealtimePipelineManager(worker_registry=registry)
    t0 = time.perf_counter()
    try:
        pipeline = manager.create_pipeline(camera_group=mock, pipeline_config=config)
        logger.info(f"Realtime pipeline created: id={pipeline.id}")

        result = drive_realtime_lockstep(
            pipeline=pipeline,
            mock_group=mock,
            num_frames=n_frames,
            per_frame_timeout=120.0,
        )
        elapsed = time.perf_counter() - t0
        fps = result.frames_processed / elapsed if elapsed > 0 else 0.0
        logger.info(
            f"Drive complete: {result.frames_processed}/{n_frames} frames  "
            f"elapsed={elapsed:.1f}s  effective_fps={fps:.1f}"
        )

        assert result.frames_processed >= int(0.9 * n_frames), (
            f"Only processed {result.frames_processed}/{n_frames} frames"
        )

        realtime_report = build_segment_length_report(
            positions_from_aggregation_outputs(result.outputs)
        )
        logger.info("[sample-data realtime] " + realtime_report.summary())

        if len(realtime_report.assessable()) >= realtime_report.thresholds.min_assessable_segments:
            violations = realtime_report.human_shape_violations(check_rigidity=False)
            if violations:
                logger.warning(f"Sample-data human-shape violations ({len(violations)}):")
                for v in violations:
                    logger.warning(f"  FAIL: {v}")
            else:
                logger.info("Sample-data realtime reconstruction is human-shaped — PASS")
            assert not violations, (
                "Sample-data realtime reconstruction is not human-shaped:\n  - "
                + "\n  - ".join(violations) + "\n" + realtime_report.summary()
            )
        else:
            logger.warning(
                f"Only {len(realtime_report.assessable())} assessable segment(s) in "
                f"{n_frames} frames — skipping human-shape assertion "
                f"(window may be calibration-heavy; use --realtime-max-frames=0 for full clip)"
            )

        logger.info("=== REALTIME SAMPLE-DATA TEST PASSED ===")
    finally:
        manager.shutdown()
        time.sleep(0.25)
        mock.close()
        logger.info("Sample-data realtime manager shut down and mock closed")
