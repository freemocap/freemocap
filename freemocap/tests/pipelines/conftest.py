"""Shared fixtures for the end-to-end pipeline tests.

These tests run the REAL posthoc + realtime pipelines against the canonical test
recording at ``FREEMOCAP_TEST_DATA_PATH`` (3 synchronized videos, 222 frames: a
7x5 charuco calibration sequence followed by mocap movement). Pipelines run
in-place in the recording folder, exactly as the app runs them.
"""
import logging
import multiprocessing
import time
from pathlib import Path

import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.charuco_tracker import CharucoBoardDefinition

from freemocap.core.kinematics.segment_lengths import (
    SegmentLengthReport,
    build_segment_length_report,
)
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.tasks.calibration.calibration_task_config import (
    PosthocCalibrationPipelineConfig,
)
from freemocap.core.tasks.calibration.shared.calibration_paths import (
    get_last_successful_calibration_toml_path,
)
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.system.default_paths import FREEMOCAP_TEST_DATA_PATH

from freemocap.tests.pipelines.anthropometry import load_posthoc_body_positions
from freemocap.tests.pipelines.helpers import wait_for_pipeline

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--realtime-max-frames",
        action="store",
        default=250,
        type=int,
        help=(
            "Cap the number of frames fed to the realtime pipeline in E2E tests "
            "(0 = all frames). Lets the longer sample-data run terminate early so "
            "you don't wait through the whole recording every time."
        ),
    )
    parser.addoption(
        "--use-sample-data",
        action="store_true",
        default=False,
        help=(
            "Run posthoc pipeline tests against freemocap_sample_data (~1100 frames) "
            "instead of the default freemocap_test_data (222 frames)."
        ),
    )


@pytest.fixture(scope="session")
def realtime_max_frames(request) -> int:
    """Frame cap for realtime E2E runs (0 = no cap). From --realtime-max-frames."""
    val = int(request.config.getoption("--realtime-max-frames"))
    logger.info(f"realtime_max_frames={val} (0 = no cap)")
    return val


@pytest.fixture(scope="session")
def sample_recording_path() -> Path:
    """The full (non-downsampled, ~1100-frame) sample recording."""
    path = Path(FREEMOCAP_TEST_DATA_PATH).parent / "freemocap_sample_data"
    logger.info(f"Looking for sample recording at: {path}")
    if not path.exists():
        logger.warning(f"Sample data not found at {path} — skipping")
        pytest.skip(f"Sample data not found at {path}")
    sync_videos = path / "synchronized_videos"
    if not sync_videos.exists() or not list(sync_videos.glob("*.mp4")):
        logger.warning(f"No synchronized_videos in {path} — skipping")
        pytest.skip(f"No synchronized_videos found in {path}")
    videos = sorted(sync_videos.glob("*.mp4"))
    logger.info(f"Sample recording found: {path} ({len(videos)} videos)")
    return path


@pytest.fixture(scope="session")
def sample_synchronized_videos_dir(sample_recording_path: Path) -> Path:
    d = sample_recording_path / "synchronized_videos"
    logger.info(f"sample_synchronized_videos_dir: {d}")
    return d


@pytest.fixture(scope="session")
def test_recording_path(request) -> Path:
    use_sample = request.config.getoption("--use-sample-data")
    if use_sample:
        path = Path(FREEMOCAP_TEST_DATA_PATH).parent / "freemocap_sample_data"
        label = "sample data (~1100 frames)"
    else:
        path = Path(FREEMOCAP_TEST_DATA_PATH)
        label = "test data (222 frames)"
    logger.info(f"test_recording_path: using {label} at {path}")
    if not path.exists():
        logger.warning(f"{label} not found at {path} — skipping")
        pytest.skip(f"{label} not found at {path}.")
    sync_videos = path / "synchronized_videos"
    if not sync_videos.exists() or not list(sync_videos.glob("*.mp4")):
        logger.warning(f"No synchronized_videos in {path} — skipping")
        pytest.skip(f"No synchronized_videos found in {path}")
    videos = sorted(sync_videos.glob("*.mp4"))
    logger.info(
        f"Recording ready: {path.name}  |  {len(videos)} videos  |  "
        + ", ".join(v.name for v in videos)
    )
    return path


@pytest.fixture(scope="session")
def synchronized_videos_dir(test_recording_path: Path) -> Path:
    d = test_recording_path / "synchronized_videos"
    logger.info(f"synchronized_videos_dir: {d}")
    return d


@pytest.fixture(scope="session")
def recording_info(test_recording_path: Path) -> RecordingInfo:
    info = RecordingInfo(
        recording_directory=str(test_recording_path.parent),
        recording_name=test_recording_path.stem,
        mic_device_index=-1,
    )
    logger.info(
        f"RecordingInfo: name={info.recording_name!r}  "
        f"directory={info.recording_directory}"
    )
    return info


@pytest.fixture(scope="session")
def charuco_board_7x5() -> CharucoBoardDefinition:
    """The board actually used to film freemocap_test_data (7x5, 58mm)."""
    board = CharucoBoardDefinition.create_test_data_7x5()
    logger.info(
        f"CharucoBoard: {board.squares_x}x{board.squares_y}  "
        f"square_length={board.square_length_mm}mm"
    )
    return board


@pytest.fixture(scope="session")
def global_kill_flag():
    flag = multiprocessing.Value("b", False)
    logger.info("Created session-scoped global_kill_flag")
    return flag


@pytest.fixture(scope="session")
def thread_worker_registry(global_kill_flag) -> WorkerRegistry:
    logger.info("Creating WorkerRegistry (THREAD mode, no heartbeat)")
    registry = WorkerRegistry(global_kill_flag=global_kill_flag, worker_mode=WorkerMode.THREAD)
    logger.info("WorkerRegistry created")
    return registry


@pytest.fixture(scope="session")
def posthoc_manager(global_kill_flag, thread_worker_registry):
    logger.info("Creating PosthocPipelineManager...")
    manager = PosthocPipelineManager(
        global_kill_flag=global_kill_flag,
        worker_registry=thread_worker_registry,
    )
    logger.info("PosthocPipelineManager ready")
    yield manager
    logger.info("Shutting down PosthocPipelineManager...")
    manager.shutdown()
    logger.info("PosthocPipelineManager shut down")


@pytest.fixture(scope="session")
def calibration_toml_path(
    recording_info: RecordingInfo,
    posthoc_manager: PosthocPipelineManager,
    charuco_board_7x5: CharucoBoardDefinition,
) -> Path:
    """Run posthoc calibration once for the session; return the last-successful TOML."""
    logger.info(
        f"=== CALIBRATION PIPELINE START ===  recording={recording_info.recording_name!r}  "
        f"board={charuco_board_7x5.squares_x}x{charuco_board_7x5.squares_y}"
    )
    t0 = time.perf_counter()
    pipeline = posthoc_manager.create_calibration_pipeline(
        recording_info=recording_info,
        calibration_config=PosthocCalibrationPipelineConfig(charuco_board=charuco_board_7x5),
    )
    logger.info(f"Calibration pipeline created: id={pipeline.id}")
    wait_for_pipeline(pipeline)
    elapsed = time.perf_counter() - t0
    logger.info(f"=== CALIBRATION PIPELINE DONE  ({elapsed:.1f}s) ===")

    toml_path = get_last_successful_calibration_toml_path()
    if not toml_path.exists():
        pytest.fail(f"Calibration completed but TOML not found at {toml_path}")
    size_kb = toml_path.stat().st_size / 1024
    logger.info(f"Calibration TOML written: {toml_path}  ({size_kb:.1f} KB)")
    return toml_path


@pytest.fixture(scope="session")
def posthoc_mocap_output_dir(
    recording_info: RecordingInfo,
    posthoc_manager: PosthocPipelineManager,
    calibration_toml_path: Path,
    test_recording_path: Path,
) -> Path:
    """Run posthoc mocap once for the session; return the output_data directory."""
    logger.info(
        f"=== MOCAP PIPELINE START ===  recording={recording_info.recording_name!r}  "
        f"calibration={calibration_toml_path.name}"
    )
    t0 = time.perf_counter()
    config = PosthocMocapPipelineConfig(
        export_to_blender=False,
        auto_open_blend_file=False,
    )
    logger.info("MocapConfig: calibration_toml_path=None (most-recent fallback)  export_to_blender=False")
    pipeline = posthoc_manager.create_mocap_pipeline(
        recording_info=recording_info,
        mocap_config=config,
    )
    logger.info(f"Mocap pipeline created: id={pipeline.id}")
    wait_for_pipeline(pipeline)
    elapsed = time.perf_counter() - t0
    logger.info(f"=== MOCAP PIPELINE DONE  ({elapsed:.1f}s) ===")

    output_dir = test_recording_path / "output_data"
    if not output_dir.exists():
        pytest.fail(f"Posthoc mocap completed but output_data not found at {output_dir}")

    npy_files = sorted(output_dir.glob("*.npy"))
    csv_files = sorted(output_dir.glob("*.csv"))
    logger.info(
        f"output_data: {output_dir}  |  "
        f"{len(npy_files)} .npy  |  {len(csv_files)} .csv"
    )
    for f in npy_files + csv_files:
        logger.info(f"  {f.name}  ({f.stat().st_size / 1024:.1f} KB)")
    return output_dir


@pytest.fixture(scope="session")
def posthoc_segment_report(posthoc_mocap_output_dir: Path) -> SegmentLengthReport:
    """Anthropometric segment-length report built from the trusted posthoc output."""
    logger.info(f"Building segment-length report from: {posthoc_mocap_output_dir}")
    positions = load_posthoc_body_positions(posthoc_mocap_output_dir)
    logger.info(f"Loaded {len(positions)} landmarks from posthoc body CSV")
    report = build_segment_length_report(positions)
    logger.info(
        f"Segment report built: {len(report.stats)} segments  |  "
        f"implied height={report.implied_height_median_mm:.0f}mm  |  "
        f"cv={report.implied_height_cv:.3f}"
    )
    logger.info("\n" + report.summary())
    return report
