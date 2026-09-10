"""Calibration recording must preserve the live inference worker and its subscriptions."""

from unittest.mock import Mock, patch
from concurrent.futures import Future
from inspect import unwrap
from queue import Queue
from types import SimpleNamespace

import numpy as np
import pytest
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.pipeline.realtime import realtime_skeleton_inference_node as inference_module
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node import RealtimeSkeletonInferenceNode
from freemocap.pubsub.pubsub_topics import PipelineConfigUpdateMessage, ProcessFrameNumberMessage, SkeletonInferenceResultMessage


def make_pipeline(*, node: Mock | None) -> RealtimePipeline:
    pipeline = object.__new__(RealtimePipeline)
    pipeline.id = 'live'
    pipeline.camera_group = Mock(id='group', camera_ids=['selected', 'excluded'])
    pipeline.config = RealtimePipelineConfig()
    pipeline.camera_nodes = {'selected': Mock()}
    pipeline.skeleton_inference_node = node
    pipeline.ipc = Mock()
    pipeline.pubsub = Mock()
    pipeline.worker_registry = Mock()
    pipeline.inference_service = Mock()
    return pipeline


def test_calibration_pause_resume_keeps_worker_and_subscriptions() -> None:
    node = Mock(is_alive=True)
    pipeline = make_pipeline(node=node)
    with patch.object(RealtimeSkeletonInferenceNode, 'create', autospec=True) as create:
        for _ in range(3):
            pipeline.enter_calibration_charuco_only_mode()
            assert not pipeline.config.camera_node_config.skeleton_tracking_enabled
            assert pipeline.skeleton_inference_node is node
            pipeline.exit_calibration_charuco_only_mode()
            assert pipeline.config.camera_node_config.skeleton_tracking_enabled
            assert pipeline.skeleton_inference_node is node
        create.assert_not_called()
    node.shutdown.assert_not_called()
    assert pipeline._pre_calibration_config is None


def test_missing_worker_is_created_with_shared_service_before_enable_is_published() -> None:
    pipeline = make_pipeline(node=None)
    node = Mock(is_alive=True)
    with patch.object(RealtimeSkeletonInferenceNode, 'create', autospec=True, return_value=node) as create:
        pipeline.update_config(new_config=pipeline.config)
    assert create.call_args.kwargs['inference_service'] is pipeline.inference_service
    assert create.call_args.kwargs['camera_ids'] == ['selected']
    node.start.assert_called_once()
    assert pipeline.skeleton_inference_node is node
    pipeline.pubsub.publish.assert_called_once()


def test_failed_resume_preserves_paused_config_and_restore_state() -> None:
    pipeline = make_pipeline(node=None)
    pipeline.enter_calibration_charuco_only_mode()
    pipeline.pubsub.publish.reset_mock()
    with patch.object(RealtimeSkeletonInferenceNode, 'create', autospec=True, side_effect=RuntimeError('inference unavailable')):
        with pytest.raises(RuntimeError, match='inference unavailable'):
            pipeline.exit_calibration_charuco_only_mode()
    assert not pipeline.config.camera_node_config.skeleton_tracking_enabled
    assert pipeline._pre_calibration_config is not None
    pipeline.pubsub.publish.assert_not_called()


def test_inference_loop_skips_paused_frames_and_resumes_without_reregistering() -> None:
    config = RealtimePipelineConfig(log_pipeline_times=False)
    paused = config.model_copy(update={'camera_node_config': config.camera_node_config.model_copy(
        update={'skeleton_tracking_enabled': False},
    )})
    updates: Queue[PipelineConfigUpdateMessage] = Queue()
    frames: Queue[ProcessFrameNumberMessage] = Queue()
    outputs: Queue[SkeletonInferenceResultMessage] = Queue()
    shutdown = SimpleNamespace(value=False)
    frame_number = 0

    def tick() -> None:
        nonlocal frame_number
        frame_number += 1
        if frame_number > 3:
            shutdown.value = True
            return
        updates.put(PipelineConfigUpdateMessage(pipeline_config=paused if frame_number == 2 else config))
        frames.put(ProcessFrameNumberMessage(frame_number=frame_number))

    future: Future[dict[str, Observation]] = Future()
    future.set_result({})
    client = Mock(failure=None)
    client.submit.return_value = future
    service = Mock()
    service.register.return_value = client
    with (
        patch.object(inference_module, 'wait_1ms', side_effect=tick),
        patch.object(inference_module.CameraGroupSharedMemory, 'recreate', return_value=Mock(valid=True)),
        patch.object(inference_module.CameraSharedMemoryRingBuffer, 'recreate', return_value=Mock(spec=inference_module.CameraSharedMemoryRingBuffer)),
        patch.object(inference_module, 'InferenceRegistration'),
        patch.object(inference_module, 'tracker_session_requests', return_value=()),
        patch.object(inference_module, '_read_frames', return_value=([np.zeros((2, 2, 3), dtype=np.uint8)], ['selected'])) as read,
    ):
        unwrap(RealtimeSkeletonInferenceNode._run)(
            camera_group_id='group', camera_ids=['selected'], pipeline_config=config,
            ipc=Mock(should_continue=True, pipeline_id='live'), shutdown_self_flag=shutdown,
            camera_group_shm_dto=Mock(camera_shm_dtos={'selected': Mock()}),
            process_frame_number_sub=frames, pipeline_config_sub=updates,
            skeleton_result_pub=outputs, timing_pub=Mock(), inference_service=service,
        )
    assert [call.kwargs['requested_frame_number'] for call in read.call_args_list] == [1, 3]
    assert [call.args[0].frame_number for call in client.submit.call_args_list] == [1, 3]
    assert [outputs.get_nowait().frame_number for _ in range(3)] == [1, 2, 3]
    service.register.assert_called_once()
    client.close.assert_called_once()
