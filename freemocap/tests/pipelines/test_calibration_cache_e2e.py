"""Realtime ChArUco observations follow the current streaming contract.

Legacy pickle consumption is covered by test_calibration_cache_alignment;
fresh posthoc calibration is covered by reference_recordings/test_fresh_posthoc.
The streaming pipeline no longer creates a legacy pickle recorder.
"""
import multiprocessing

import numpy as np
import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.tests.pipelines.mocks.mock_camera_group import MockCameraGroup
from freemocap.tests.pipelines.mocks.realtime_driver import drive_realtime_lockstep


@pytest.mark.e2e
def test_realtime_charuco_observations_preserve_recording_frames(
    synchronized_videos_dir, charuco_board_7x5,
):
    config = RealtimePipelineConfig(
        camera_node_config=CameraNodeConfig(
            worker_mode=WorkerMode.THREAD,
            charuco_tracking_enabled=True,
            skeleton_tracking_enabled=False,
            charuco_board=charuco_board_7x5,
        ),
        aggregator_config=RealtimeAggregatorNodeConfig(
            triangulation_enabled=False, skeleton_fitting_enabled=False,
            center_of_mass_enabled=False,
        ),
        use_centralized_inference=False, log_pipeline_times=False,
    )
    flag = multiprocessing.Value("b", False)
    registry = WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.THREAD)
    service = InferenceService(worker_registry=registry)
    manager = RealtimePipelineManager(worker_registry=registry, inference_service=service)
    group = None
    try:
        registry.start_heartbeat()
        group = MockCameraGroup.create(
            synchronized_videos_dir=synchronized_videos_dir, global_kill_flag=flag,
        )
        assert group.frame_count == 222
        assert len(group.camera_ids) == 3
        service.start()
        pipeline = manager.create_pipeline(camera_group=group, pipeline_config=config)
        assert pipeline.charuco_recorder_node is None
        result = drive_realtime_lockstep(
            pipeline=pipeline, mock_group=group, num_frames=group.frame_count,
            per_frame_timeout=30.0,
        )
        assert result.frames_written == result.frames_processed == 222
        assert [output.frame_number for output in result.outputs] == list(range(222))
        assert pipeline.failure is None
        detections = dict.fromkeys(group.camera_ids, 0)
        for output in result.outputs:
            assert set(output.camera_node_outputs) == set(group.camera_ids)
            for camera_id, camera in output.camera_node_outputs.items():
                assert camera.frame_number == output.frame_number
                assert camera.skeleton_observation is None
                observation = camera.charuco_observation
                if observation is None:
                    continue
                assert observation.frame_number == output.frame_number
                stage = observation.stages.get("charuco")
                if stage is not None and stage.keypoints is not None:
                    assert stage.keypoints.names == charuco_board_7x5.all_point_names
                    if np.isfinite(stage.keypoints.xyz[:, :2]).all(axis=1).any():
                        detections[camera_id] += 1
        assert all(count > 0 for count in detections.values()), detections
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
