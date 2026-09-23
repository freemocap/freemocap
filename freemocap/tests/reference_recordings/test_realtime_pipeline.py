"""Deterministic video replay through core's real realtime processing workers.

Capture is replaced at shared-memory input; this is not a SkellyCam capture or
wall-clock throughput test. Temporal filtering is disabled for decimated replay.
"""

import multiprocessing
from multiprocessing import shared_memory

import numpy as np
import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.skeletons.charuco_board_skeleton import CHARUCO_BOARD_MODEL_ID
from freemocap.core.skeletons.standard_human_skeleton import STANDARD_HUMAN_MODEL_ID
from freemocap.core.tasks.calibration.shared.calibration_paths import find_recording_calibration
from freemocap.tests.pipelines.mocks.mock_camera_group import MockCameraGroup
from freemocap.tests.pipelines.mocks.realtime_driver import drive_realtime_lockstep
from freemocap.tests.recording_datasets import synchronized_video_directory


def shared_memory_names(group):
    names = []
    for camera in group.shm.to_dto().camera_shm_dtos.values():
        for element in (camera.ring_shm_dto, camera.last_written_index_shm_dto, camera.last_read_index_shm_dto):
            names.extend((element.shm_name, element.shm_valid_name, element.first_written_shm_name))
    return names


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.parametrize("human_enabled", [False, True], ids=["charuco", "charuco-and-human"])
def test_realtime_replay_preserves_frames_and_reconstructs(prepared_reference, human_enabled):
    calibration = find_recording_calibration(recording_folder=prepared_reference.full_path)
    assert calibration is not None
    config = RealtimePipelineConfig(
        camera_node_config=CameraNodeConfig(
            worker_mode=WorkerMode.THREAD, charuco_board=CharucoBoardDefinition.create_test_data_7x5(),
            charuco_tracking_enabled=True, skeleton_tracking_enabled=human_enabled,
            enable_keypoint_filter=False,
        ),
        aggregator_config=RealtimeAggregatorNodeConfig(
            calibration_toml_path=str(calibration), triangulation_enabled=True,
            skeleton_fitting_enabled=True, center_of_mass_enabled=human_enabled, filter_enabled=False,
        ),
        use_centralized_inference=True, log_pipeline_times=False,
    )
    flag = multiprocessing.Value("b", False)
    registry = WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.THREAD)
    service = InferenceService(worker_registry=registry)
    manager = RealtimePipelineManager(worker_registry=registry, inference_service=service)
    group = None
    names = []
    try:
        registry.start_heartbeat()
        group = MockCameraGroup.create(
            synchronized_videos_dir=synchronized_video_directory(prepared_reference.full_path),
            global_kill_flag=flag,
        )
        names = shared_memory_names(group)
        assert group.frame_count == 222
        service.start()
        pipeline = manager.create_pipeline(camera_group=group, pipeline_config=config)
        driven = drive_realtime_lockstep(pipeline=pipeline, mock_group=group,
                                        num_frames=222, per_frame_timeout=120.0)
        assert [output.frame_number for output in driven.outputs] == list(range(222))
        assert driven.frames_written == driven.frames_processed == 222
        assert pipeline.failure is None
        assert all(output.pipeline_id == pipeline.id for output in driven.outputs)
        assert all(set(output.camera_node_outputs) == set(group.camera_ids) for output in driven.outputs)
        assert all(output.calibration_applicable for output in driven.outputs)
        assert all(camera.frame_number == output.frame_number for output in driven.outputs
                   for camera in output.camera_node_outputs.values())
        expected_models = [CHARUCO_BOARD_MODEL_ID]
        if human_enabled:
            expected_models.append(STANDARD_HUMAN_MODEL_ID)
        else:
            assert all(STANDARD_HUMAN_MODEL_ID not in output.reconstructions for output in driven.outputs)
        for model_id in expected_models:
            reconstructed = [output.reconstructions[model_id] for output in driven.outputs
                             if model_id in output.reconstructions]
            assert reconstructed, f"No reconstruction for {model_id}"
            assert any(np.isfinite(point).all() for item in reconstructed for point in item.landmarks.values()), model_id
            rotations = [q for item in reconstructed for q in item.segment_rotations_world.values()
                         if np.isfinite(q).all()]
            assert rotations, f"No finite orientations for {model_id}"
            np.testing.assert_allclose(np.linalg.norm(rotations, axis=1), 1.0, atol=1e-6)
            assert any(item.fitted_scale_mm is not None and np.isfinite(item.fitted_scale_mm)
                       and item.fitted_scale_mm > 0 for item in reconstructed), model_id
    finally:
        try:
            manager.shutdown()
        finally:
            try:
                service.close()
            finally:
                try:
                    registry.shutdown_all()
                finally:
                    if group is not None:
                        group.close()
        assert not registry.alive_workers, "Realtime workers survived shutdown"
        for name in names:
            try:
                leaked = shared_memory.SharedMemory(name=name)
            except FileNotFoundError:
                continue
            leaked.close()
            pytest.fail(f"Shared memory survived shutdown: {name}")
