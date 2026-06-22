"""E2E: realtime pipeline driven by a mock camera group feeding the test videos.

The MockCameraGroup creates REAL skellycam shared memory and feeds it frames read
from the recorded videos; the realtime camera nodes, aggregator, triangulation
and skeleton-fitting run unmodified. A single-threaded lockstep driver processes
every frame deterministically.

Parametrized:
  - ``charuco_only`` (fast): exercises feeder -> camera node -> aggregator
    plumbing + charuco triangulation. No pose model.
  - ``full`` (slow): adds RTMPose skeleton detection + triangulation + fitting.
"""
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


def _assert_realtime_human_shaped_and_matches_posthoc(outputs, request) -> None:
    """Validate the realtime RAW reconstruction is human-shaped and ~ posthoc.

    Uses the raw triangulated keypoints (pre-FABRIK) — the honest reconstruction.
    Rigidity is not checked here (raw per-frame triangulation jitters; FABRIK is
    what enforces rigidity downstream). Proportions, symmetry, plausible scale,
    and per-limb-median equivalence to the trusted posthoc output ARE checked.
    """
    realtime_report = build_segment_length_report(
        positions_from_aggregation_outputs(outputs)
    )
    print("\n[realtime] " + realtime_report.summary())

    shape_violations = realtime_report.human_shape_violations(check_rigidity=False)
    assert not shape_violations, (
        "Realtime raw reconstruction is not human-shaped:\n  - "
        + "\n  - ".join(shape_violations) + "\n" + realtime_report.summary()
    )

    posthoc_report = request.getfixturevalue("posthoc_segment_report")
    eq_violations = equivalence_violations(
        realtime_report, posthoc_report, label_a="realtime", label_b="posthoc",
    )
    assert not eq_violations, (
        "Realtime segment lengths differ from posthoc:\n  - "
        + "\n  - ".join(eq_violations)
        + "\n[realtime] " + realtime_report.summary()
        + "\n[posthoc]  " + posthoc_report.summary()
    )


def _build_pipeline_config(mode: str, charuco_board) -> RealtimePipelineConfig:
    charuco_enabled = mode in ("charuco_only", "full")
    skeleton_enabled = mode == "full"
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
        use_centralized_gpu_inference=False,  # per-camera RTMPose; no dedicated GPU/TRT node
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
    # Isolated kill flag + registry: a failure here can't poison other tests, and
    # the mock's shm shares the exact kill flag the workers watch.
    kill_flag = multiprocessing.Value("b", False)
    registry = WorkerRegistry(global_kill_flag=kill_flag, worker_mode=WorkerMode.THREAD)

    config = _build_pipeline_config(mode, charuco_board_7x5)
    mock = MockCameraGroup.create(
        synchronized_videos_dir=synchronized_videos_dir,
        global_kill_flag=kill_flag,
    )
    manager = RealtimePipelineManager(worker_registry=registry)
    try:
        pipeline = manager.create_pipeline(camera_group=mock, pipeline_config=config)
        result = drive_realtime_lockstep(
            pipeline=pipeline,
            mock_group=mock,
            num_frames=mock.frame_count,
            per_frame_timeout=per_frame_timeout,
        )

        assert result.frames_processed >= int(0.9 * mock.frame_count), (
            f"Only processed {result.frames_processed}/{mock.frame_count} frames"
        )
        assert any(len(o.keypoints_arrays) > 0 for o in result.outputs), (
            "No frame produced triangulated 3D keypoints (calibration may not have loaded)"
        )
        if mode == "full":
            assert any(o.skeleton for o in result.outputs), "No fitted skeleton produced"
            assert any(o.center_of_mass_result is not None for o in result.outputs), (
                "No center-of-mass result produced"
            )
            _assert_realtime_human_shaped_and_matches_posthoc(result.outputs, request)
    finally:
        manager.shutdown()
        time.sleep(0.25)  # let worker threads observe shutdown before we unlink shm
        mock.close()


@pytest.mark.e2e
@pytest.mark.slow
def test_realtime_pipeline_on_sample_data(
    sample_synchronized_videos_dir, charuco_board_7x5, calibration_toml_path,
    realtime_max_frames,
):
    """Exercise the realtime pipeline over the longer (non-downsampled) sample
    recording. Capped to --realtime-max-frames (default 250, 0 = all) so it
    terminates early by default. Reuses the test-data calibration — the sample
    recording is the same physical cameras/setup, so the calibration applies.
    """
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
    print(f"\n[sample-data] driving {n_frames}/{mock.frame_count} frames")

    manager = RealtimePipelineManager(worker_registry=registry)
    try:
        pipeline = manager.create_pipeline(camera_group=mock, pipeline_config=config)
        result = drive_realtime_lockstep(
            pipeline=pipeline,
            mock_group=mock,
            num_frames=n_frames,
            per_frame_timeout=120.0,
        )
        assert result.frames_processed >= int(0.9 * n_frames), (
            f"Only processed {result.frames_processed}/{n_frames} frames"
        )
        # The sample recording is a real person; validate human-shape WHEN the
        # processed window has enough body data (a small cap from the start may be
        # calibration-heavy). Throughput is always asserted above; equivalence vs
        # posthoc is covered by the test-data run.
        realtime_report = build_segment_length_report(
            positions_from_aggregation_outputs(result.outputs)
        )
        print("\n[sample-data realtime] " + realtime_report.summary())
        if len(realtime_report.assessable()) >= realtime_report.thresholds.min_assessable_segments:
            violations = realtime_report.human_shape_violations(check_rigidity=False)
            assert not violations, (
                "Sample-data realtime reconstruction is not human-shaped:\n  - "
                + "\n  - ".join(violations) + "\n" + realtime_report.summary()
            )
        else:
            print(
                f"[sample-data] only {len(realtime_report.assessable())} assessable "
                f"segment(s) in {n_frames} frames — skipping human-shape assertion "
                f"(window may be calibration-heavy; use --realtime-max-frames=0 for the full clip)"
            )
    finally:
        manager.shutdown()
        time.sleep(0.25)
        mock.close()
