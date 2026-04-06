"""
End-to-end pipeline tests: calibration → mocap → blender export.

These tests run the full real pipeline against FREEMOCAP_TEST_DATA_PATH.
They are marked with @pytest.mark.e2e and require test data on disk.

Run with:
    pytest freemocap/tests/test_e2e_pipeline.py -v -s --timeout=600

Skip in fast CI with:
    pytest freemocap/tests/ -m "not e2e"
"""
import multiprocessing
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.calibration.shared.calibration_paths import (
    get_last_successful_calibration_toml_path,
)
from freemocap.core.pipeline.pipeline_configs import (
    CalibrationPipelineConfig,
    MocapPipelineConfig,
)
from freemocap.core.pipeline.posthoc.posthoc_pipeline import PosthocPipeline
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.system.default_paths import FREEMOCAP_TEST_DATA_PATH

PIPELINE_TIMEOUT_SECONDS = 600


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait_for_pipeline(pipeline: PosthocPipeline, timeout: float = PIPELINE_TIMEOUT_SECONDS) -> None:
    """Poll until the pipeline finishes or timeout is reached."""
    start = time.monotonic()
    while pipeline.alive:
        if time.monotonic() - start > timeout:
            pipeline.shutdown()
            raise TimeoutError(
                f"Pipeline [{pipeline.id}] did not complete within {timeout}s"
            )
        time.sleep(1.0)


def _recording_info_from_path(recording_path: Path) -> RecordingInfo:
    return RecordingInfo(
        recording_directory=str(recording_path.parent),
        recording_name=recording_path.stem,
        mic_device_index=-1,
    )


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_data_path() -> Path:
    path = Path(FREEMOCAP_TEST_DATA_PATH)
    if not path.exists():
        pytest.skip(
            f"Test data not found at {path}. "
            "Download it first or set FREEMOCAP_TEST_DATA_PATH."
        )
    sync_videos = path / "synchronized_videos"
    if not sync_videos.exists() or not list(sync_videos.glob("*.mp4")):
        pytest.skip(f"No synchronized_videos found in {path}")
    return path


@pytest.fixture(scope="session")
def global_kill_flag():
    return multiprocessing.Value("b", False)


@pytest.fixture(scope="session")
def worker_registry(global_kill_flag):
    return WorkerRegistry(
        global_kill_flag=global_kill_flag,
        worker_mode=WorkerMode.THREAD,
    )


@pytest.fixture(scope="session")
def pipeline_manager(global_kill_flag, worker_registry) -> PosthocPipelineManager:
    manager = PosthocPipelineManager(
        global_kill_flag=global_kill_flag,
        worker_registry=worker_registry,
    )
    yield manager
    manager.shutdown()


@pytest.fixture(scope="session")
def calibration_toml_path(test_data_path: Path, pipeline_manager: PosthocPipelineManager) -> Path:
    """
    Run calibration once for the whole test session.
    Returns the path to the written calibration TOML.
    """
    recording_info = _recording_info_from_path(test_data_path)
    pipeline = pipeline_manager.create_calibration_pipeline(
        recording_info=recording_info,
        calibration_config=CalibrationPipelineConfig(),
    )
    _wait_for_pipeline(pipeline)

    toml_path = get_last_successful_calibration_toml_path()
    if not toml_path.exists():
        pytest.fail(f"Calibration completed but TOML not found at {toml_path}")
    return toml_path


# ---------------------------------------------------------------------------
# Calibration pipeline tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestCalibrationPipeline:

    def test_calibration_produces_toml_in_recording_folder(
        self, test_data_path: Path, calibration_toml_path: Path
    ) -> None:
        # calibration_toml_path fixture already ran calibration; verify recording-local copy
        expected = test_data_path / f"{test_data_path.stem}_camera_calibration.toml"
        assert expected.exists(), f"Expected recording-local TOML at {expected}"

    def test_calibration_updates_last_successful_toml(
        self, calibration_toml_path: Path
    ) -> None:
        assert calibration_toml_path.exists(), (
            f"last_successful_camera_calibration.toml not found at {calibration_toml_path}"
        )
        assert calibration_toml_path.stat().st_size > 0

    def test_calibration_annotated_videos_match_source_resolution_and_frame_count(
        self, test_data_path: Path, calibration_toml_path: Path
    ) -> None:
        annotated_dir = test_data_path / "annotated_videos"
        assert annotated_dir.exists(), f"annotated_videos/ not found in {test_data_path}"

        sync_videos_dir = test_data_path / "synchronized_videos"
        source_videos = sorted(sync_videos_dir.glob("*.mp4"))
        annotated_videos = sorted(annotated_dir.glob("*.mp4"))

        assert len(annotated_videos) > 0, "No annotated videos produced"
        assert len(annotated_videos) == len(source_videos), (
            f"Annotated video count ({len(annotated_videos)}) != "
            f"source video count ({len(source_videos)})"
        )

        for ann_path, src_path in zip(annotated_videos, source_videos):
            ann = cv2.VideoCapture(str(ann_path))
            src = cv2.VideoCapture(str(src_path))
            try:
                ann_w = int(ann.get(cv2.CAP_PROP_FRAME_WIDTH))
                ann_h = int(ann.get(cv2.CAP_PROP_FRAME_HEIGHT))
                ann_n = int(ann.get(cv2.CAP_PROP_FRAME_COUNT))
                src_w = int(src.get(cv2.CAP_PROP_FRAME_WIDTH))
                src_h = int(src.get(cv2.CAP_PROP_FRAME_HEIGHT))
                src_n = int(src.get(cv2.CAP_PROP_FRAME_COUNT))
                assert ann_w == src_w, f"{ann_path.name}: width {ann_w} != {src_w}"
                assert ann_h == src_h, f"{ann_path.name}: height {ann_h} != {src_h}"
                assert ann_n == src_n, f"{ann_path.name}: frames {ann_n} != {src_n}"
            finally:
                ann.release()
                src.release()


# ---------------------------------------------------------------------------
# Mocap pipeline tests
# ---------------------------------------------------------------------------


def _run_mocap_and_wait(
    test_data_path: Path,
    pipeline_manager: PosthocPipelineManager,
    calibration_toml_path_override: str | None,
) -> None:
    mocap_config = MocapPipelineConfig.default_posthoc()
    if calibration_toml_path_override is not None:
        mocap_config = mocap_config.model_copy(
            update={"calibration_toml_path": calibration_toml_path_override}
        )
    recording_info = _recording_info_from_path(test_data_path)
    pipeline = pipeline_manager.create_mocap_pipeline(
        recording_info=recording_info,
        mocap_config=mocap_config,
    )
    _wait_for_pipeline(pipeline)


@pytest.mark.e2e
class TestMocapPipeline:

    @pytest.fixture(scope="class", autouse=True)
    def run_mocap_implicit_calibration(
        self, test_data_path: Path, pipeline_manager: PosthocPipelineManager, calibration_toml_path: Path
    ) -> None:
        """Run mocap using the implicit 'most recent calibration' (None path)."""
        _run_mocap_and_wait(test_data_path, pipeline_manager, calibration_toml_path_override=None)

    def test_output_data_folder_exists(self, test_data_path: Path) -> None:
        output_dir = test_data_path / "output_data"
        assert output_dir.exists(), f"output_data/ not found in {test_data_path}"

    def test_npy_files_present(self, test_data_path: Path) -> None:
        output_dir = test_data_path / "output_data"
        npy_files = list(output_dir.glob("*.npy"))
        assert len(npy_files) > 0, f"No .npy files found in {output_dir}"

    def test_csv_files_present(self, test_data_path: Path) -> None:
        output_dir = test_data_path / "output_data"
        csv_files = list(output_dir.glob("*.csv"))
        assert len(csv_files) > 0, f"No .csv files found in {output_dir}"

    def test_body_npy_has_correct_shape(self, test_data_path: Path) -> None:
        output_dir = test_data_path / "output_data"
        npy_files = list(output_dir.glob("*.npy"))
        # Find the main body 3D data file
        body_files = [f for f in npy_files if "body" in f.stem.lower() and "3d" in f.stem.lower()]
        if not body_files:
            body_files = [f for f in npy_files if "body" in f.stem.lower()]
        assert body_files, f"No body npy found in {output_dir}. Files: {[f.name for f in npy_files]}"
        data = np.load(body_files[0])
        assert data.ndim >= 2, f"Expected at least 2D array, got shape {data.shape}"
        assert not np.all(np.isnan(data)), "Body data is all NaN — triangulation likely failed"

    def test_mocap_annotated_videos_match_source(self, test_data_path: Path) -> None:
        annotated_dir = test_data_path / "annotated_videos"
        sync_dir = test_data_path / "synchronized_videos"
        if not annotated_dir.exists():
            pytest.skip("annotated_videos/ not present (may be skipped in config)")
        source_videos = sorted(sync_dir.glob("*.mp4"))
        annotated_videos = sorted(annotated_dir.glob("*.mp4"))
        assert len(annotated_videos) == len(source_videos)
        for ann_path, src_path in zip(annotated_videos, source_videos):
            ann = cv2.VideoCapture(str(ann_path))
            src = cv2.VideoCapture(str(src_path))
            try:
                assert int(ann.get(cv2.CAP_PROP_FRAME_WIDTH)) == int(src.get(cv2.CAP_PROP_FRAME_WIDTH))
                assert int(ann.get(cv2.CAP_PROP_FRAME_HEIGHT)) == int(src.get(cv2.CAP_PROP_FRAME_HEIGHT))
                assert int(ann.get(cv2.CAP_PROP_FRAME_COUNT)) == int(src.get(cv2.CAP_PROP_FRAME_COUNT))
            finally:
                ann.release()
                src.release()


@pytest.mark.e2e
class TestMocapWithExplicitCalibrationPath:
    """Re-run mocap with an explicitly provided calibration TOML path."""

    @pytest.fixture(scope="class", autouse=True)
    def run_mocap_explicit_calibration(
        self,
        test_data_path: Path,
        pipeline_manager: PosthocPipelineManager,
        calibration_toml_path: Path,
    ) -> None:
        _run_mocap_and_wait(
            test_data_path,
            pipeline_manager,
            calibration_toml_path_override=str(calibration_toml_path),
        )

    def test_output_data_folder_exists(self, test_data_path: Path) -> None:
        output_dir = test_data_path / "output_data"
        assert output_dir.exists()

    def test_npy_files_present(self, test_data_path: Path) -> None:
        output_dir = test_data_path / "output_data"
        assert len(list(output_dir.glob("*.npy"))) > 0

    def test_csv_files_present(self, test_data_path: Path) -> None:
        output_dir = test_data_path / "output_data"
        assert len(list(output_dir.glob("*.csv"))) > 0


# ---------------------------------------------------------------------------
# Blender export tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestBlenderExport:

    @pytest.fixture(scope="class", autouse=True)
    def run_blender_export(
        self, test_data_path: Path, calibration_toml_path: Path
    ) -> None:
        """Run blender export after mocap has produced output_data/."""
        from freemocap.core.blender.export_to_blender import export_to_blender

        output_dir = test_data_path / "output_data"
        if not output_dir.exists() or not list(output_dir.glob("*.npy")):
            pytest.skip("output_data/ not present — run mocap tests first")

        export_to_blender(recording_folder_path=str(test_data_path))

    def test_blend_file_exists(self, test_data_path: Path) -> None:
        blend_file = test_data_path / f"{test_data_path.stem}.blend"
        assert blend_file.exists(), f"Expected .blend file at {blend_file}"

    def test_blend_file_is_non_empty(self, test_data_path: Path) -> None:
        blend_file = test_data_path / f"{test_data_path.stem}.blend"
        assert blend_file.stat().st_size > 0, ".blend file is empty"
