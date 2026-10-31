"""Failure cleanup must stay local to a pipeline, including dead workers."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from freemocap.core.pipeline.realtime import realtime_pipeline as module


def test_filter_adjustments_survive_calibration_recording_mode():
    from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig
    pipeline = object.__new__(module.RealtimePipeline)
    pipeline.id = 'filter-restore'
    pipeline.config = module.RealtimePipelineConfig(use_centralized_inference=False)
    pipeline._pre_calibration_config = pipeline.config.model_copy(deep=True)
    pipeline._pre_calibration_config.camera_node_config.skeleton_tracking_enabled = True
    pipeline.config.camera_node_config.skeleton_tracking_enabled = False
    requested = RealtimeFilterConfig(gap_duration_s=0.5, segment_retention_s=0.5)
    pipeline.config.aggregator_config.realtime_filter_config = requested
    pipeline.skeleton_inference_node = None
    pipeline.pubsub = Mock()
    pipeline.exit_calibration_charuco_only_mode()
    assert pipeline.config.camera_node_config.skeleton_tracking_enabled
    assert pipeline.config.aggregator_config.realtime_filter_config == requested
    assert pipeline._pre_calibration_config is None
    pipeline.pubsub.publish.assert_called_once()


def test_invalid_recording_timing_closes_replay_videos(tmp_path):
    from freemocap.tests.pipelines.mocks import mock_camera_group as replay
    (tmp_path / 'camera.mp4').touch()
    videos = Mock(spec=replay.VideoGroupHelper)
    videos.videos = {}
    videos.video_metadata_by_id = {}
    videos.frame_count = 1
    with patch.object(replay.VideoGroupHelper, 'from_video_paths', return_value=videos), \
         patch.object(replay, 'build_camera_configs_from_videos', return_value={}), \
         patch.object(replay.RecordingGroupTiming, 'resolve', side_effect=ValueError('invalid timing')):
        with pytest.raises(ValueError, match='invalid timing'):
            replay.MockCameraGroup.create(synchronized_videos_dir=str(tmp_path), global_kill_flag=Mock())
    videos.close.assert_called_once()

def node():
    result = Mock()
    result.is_alive = False
    return result


@pytest.mark.parametrize("failure_stage", ["camera", "aggregation"])
def test_construction_failure_releases_owned_resources(failure_stage):
    group = Mock(spec=module.CaptureGroup)
    group.id = "group"
    group.ipc = SimpleNamespace(global_kill_flag=Mock())
    group.configs = {"a": Mock(), "b": Mock()}
    group.shm = Mock()
    group.shm.to_dto.return_value.camera_shm_dtos = {"a": Mock(), "b": Mock()}
    registry = Mock(spec=module.WorkerRegistry)
    registry.heartbeat_timestamp = Mock()
    service = Mock(spec=module.InferenceService)
    ipc, pubsub = Mock(), Mock()
    first, second = node(), node()
    config = module.RealtimePipelineConfig(camera_node_config={"skeleton_tracking_enabled": False})
    camera_results = [first, RuntimeError("construction failed")] if failure_stage == "camera" else [first, second]
    with patch.object(module.PipelineIPC, "create", return_value=ipc), \
         patch.object(module.PubSubTopicManager, "create", return_value=pubsub), \
         patch.object(module.CameraNode, "create", side_effect=camera_results), \
         patch.object(module.RealtimeAggregatorNode, "create", side_effect=RuntimeError("construction failed")):
        with pytest.raises(RuntimeError, match="construction failed"):
            module.RealtimePipeline.create(camera_group=group, worker_registry=registry,
                                           pipeline_config=config, inference_service=service)
    first.shutdown.assert_called_once()
    if failure_stage == "aggregation":
        second.shutdown.assert_called_once()
    ipc.shutdown_pipeline.assert_called_once()
    pubsub.close.assert_called_once()
    registry.shutdown_all.assert_not_called()
    assert not service.method_calls
    group.close_transport.assert_called_once()
    assert all(call[0].startswith("shm.") or call[0] == "close_transport" for call in group.method_calls)


def test_partial_start_failure_releases_nodes_without_stopping_shared_owners():
    pipeline = object.__new__(module.RealtimePipeline)
    pipeline.id = "test"
    pipeline.started = False
    pipeline.camera_group = Mock()
    pipeline.camera_group.id = "group"
    pipeline.camera_group.started = True
    pipeline.camera_nodes = {"a": node(), "b": node()}
    pipeline.camera_nodes["b"].start.side_effect = RuntimeError("start failed")
    pipeline.aggregation_node = node()
    pipeline.skeleton_inference_node = node()
    pipeline.charuco_recorder_node = None
    pipeline.ipc, pipeline.pubsub = Mock(), Mock()
    pipeline.inference_service, pipeline.worker_registry = Mock(), Mock()
    with pytest.raises(RuntimeError, match="start failed"):
        pipeline.start()
    for owned in [*pipeline.camera_nodes.values(), pipeline.aggregation_node, pipeline.skeleton_inference_node]:
        owned.shutdown.assert_called_once()
    pipeline.pubsub.close.assert_called_once()
    assert not pipeline.started
    assert not pipeline.inference_service.method_calls
    assert not pipeline.worker_registry.method_calls
    pipeline.camera_group.shutdown.assert_not_called()


def test_cleanup_attempts_other_nodes_but_keeps_queues_for_live_reader():
    failed, stopped = node(), node()
    failed.is_alive = True
    failed.shutdown.side_effect = RuntimeError("thread did not exit")
    pubsub = Mock()
    with pytest.raises(ExceptionGroup, match="cleanup failed"):
        module._shutdown_pipeline_nodes(ipc=Mock(), nodes=[failed, stopped], pubsub=pubsub)
    stopped.shutdown.assert_called_once()
    pubsub.close.assert_not_called()
