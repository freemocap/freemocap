"""Failure cleanup must stay local to a pipeline, including dead workers."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from freemocap.core.pipeline.realtime import realtime_pipeline as module


def node():
    result = Mock()
    result.is_alive = False
    return result


@pytest.mark.parametrize("failure_stage", ["camera", "aggregation"])
def test_construction_failure_releases_owned_resources(failure_stage):
    group = Mock(spec=module.CameraGroup)
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
    assert all(call[0].startswith("shm.") for call in group.method_calls)


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
