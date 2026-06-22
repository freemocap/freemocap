"""Shared fixtures for the end-to-end pipeline tests.

These tests run the REAL posthoc + realtime pipelines against the canonical test
recording at ``FREEMOCAP_TEST_DATA_PATH`` (3 synchronized videos, 222 frames: a
7x5 charuco calibration sequence followed by mocap movement). Pipelines run
in-place in the recording folder, exactly as the app runs them.
"""
import multiprocessing
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
    CalibrationSource,
    PosthocCalibrationPipelineConfig,
)
from freemocap.core.tasks.calibration.shared.calibration_paths import (
    get_last_successful_calibration_toml_path,
)
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.system.default_paths import FREEMOCAP_TEST_DATA_PATH

from freemocap.tests.pipelines.anthropometry import load_posthoc_body_positions
from freemocap.tests.pipelines.helpers import wait_for_pipeline


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


@pytest.fixture(scope="session")
def realtime_max_frames(request) -> int:
    """Frame cap for realtime E2E runs (0 = no cap). From --realtime-max-frames."""
    return int(request.config.getoption("--realtime-max-frames"))


@pytest.fixture(scope="session")
def sample_recording_path() -> Path:
    """The full (non-downsampled, ~1100-frame) sample recording — same cameras as
    the test data, useful for exercising the realtime pipeline over a longer run."""
    path = Path(FREEMOCAP_TEST_DATA_PATH).parent / "freemocap_sample_data"
    if not path.exists():
        pytest.skip(f"Sample data not found at {path}")
    sync_videos = path / "synchronized_videos"
    if not sync_videos.exists() or not list(sync_videos.glob("*.mp4")):
        pytest.skip(f"No synchronized_videos found in {path}")
    return path


@pytest.fixture(scope="session")
def sample_synchronized_videos_dir(sample_recording_path: Path) -> Path:
    return sample_recording_path / "synchronized_videos"


@pytest.fixture(scope="session")
def test_recording_path() -> Path:
    path = Path(FREEMOCAP_TEST_DATA_PATH)
    if not path.exists():
        pytest.skip(
            f"Test data not found at {path}. "
            "Download it or set FREEMOCAP_TEST_DATA_PATH."
        )
    sync_videos = path / "synchronized_videos"
    if not sync_videos.exists() or not list(sync_videos.glob("*.mp4")):
        pytest.skip(f"No synchronized_videos found in {path}")
    return path


@pytest.fixture(scope="session")
def synchronized_videos_dir(test_recording_path: Path) -> Path:
    return test_recording_path / "synchronized_videos"


@pytest.fixture(scope="session")
def recording_info(test_recording_path: Path) -> RecordingInfo:
    return RecordingInfo(
        recording_directory=str(test_recording_path.parent),
        recording_name=test_recording_path.stem,
        mic_device_index=-1,
    )


@pytest.fixture(scope="session")
def charuco_board_7x5() -> CharucoBoardDefinition:
    """The board actually used to film freemocap_test_data (7x5, 58mm)."""
    return CharucoBoardDefinition.create_test_data_7x5()


@pytest.fixture(scope="session")
def global_kill_flag():
    return multiprocessing.Value("b", False)


@pytest.fixture(scope="session")
def thread_worker_registry(global_kill_flag) -> WorkerRegistry:
    # THREAD mode keeps the posthoc workers in-process. We deliberately do NOT
    # call start_heartbeat(): its child-monitor thread sends SIGTERM to our own
    # process on worker death / a set kill flag, which would tear down pytest.
    return WorkerRegistry(global_kill_flag=global_kill_flag, worker_mode=WorkerMode.THREAD)


@pytest.fixture(scope="session")
def posthoc_manager(global_kill_flag, thread_worker_registry):
    manager = PosthocPipelineManager(
        global_kill_flag=global_kill_flag,
        worker_registry=thread_worker_registry,
    )
    yield manager
    manager.shutdown()


@pytest.fixture(scope="session")
def calibration_toml_path(
    recording_info: RecordingInfo,
    posthoc_manager: PosthocPipelineManager,
    charuco_board_7x5: CharucoBoardDefinition,
) -> Path:
    """Run posthoc calibration once for the session; return the last-successful TOML.

    Prerequisite for the mocap and realtime tests — the realtime aggregator loads
    calibration from this global path via CalibrationStateTracker.
    """
    pipeline = posthoc_manager.create_calibration_pipeline(
        recording_info=recording_info,
        calibration_config=PosthocCalibrationPipelineConfig(charuco_board=charuco_board_7x5),
    )
    wait_for_pipeline(pipeline)
    toml_path = get_last_successful_calibration_toml_path()
    if not toml_path.exists():
        pytest.fail(f"Calibration completed but TOML not found at {toml_path}")
    return toml_path


@pytest.fixture(scope="session")
def posthoc_mocap_output_dir(
    recording_info: RecordingInfo,
    posthoc_manager: PosthocPipelineManager,
    calibration_toml_path: Path,
    test_recording_path: Path,
) -> Path:
    """Run posthoc mocap once for the session (most-recent calibration, no Blender);
    return the output_data directory. Shared by the mocap, anthropometry, and
    realtime-equivalence tests so mocap runs only once."""
    config = PosthocMocapPipelineConfig(
        calibration_source=CalibrationSource.MOST_RECENT,
        export_to_blender=False,
        auto_open_blend_file=False,
    )
    pipeline = posthoc_manager.create_mocap_pipeline(
        recording_info=recording_info,
        mocap_config=config,
    )
    wait_for_pipeline(pipeline)
    output_dir = test_recording_path / "output_data"
    if not output_dir.exists():
        pytest.fail(f"Posthoc mocap completed but output_data not found at {output_dir}")
    return output_dir


@pytest.fixture(scope="session")
def posthoc_segment_report(posthoc_mocap_output_dir: Path) -> SegmentLengthReport:
    """Anthropometric segment-length report built from the trusted posthoc output.

    Serves as both the human-shape reference and the comparison target for the
    realtime pipeline.
    """
    positions = load_posthoc_body_positions(posthoc_mocap_output_dir)
    return build_segment_length_report(positions)
