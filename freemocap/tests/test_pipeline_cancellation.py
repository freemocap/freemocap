from freemocap.core.pipeline.inference_service import InferenceService
"""Cancellation endpoints preserve unrelated task and mode scopes."""

import multiprocessing
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.api.http.mocap.mocap_router import mocap_router
from freemocap.api.http.calibration.calibration_router import calibration_router
from freemocap.core.pipeline.posthoc.posthoc_pipeline import PosthocPipeline
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.posthoc.pipeline_phases import PosthocPipelineType
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase
from freemocap.core.pipeline.posthoc.progress_messages import AggregatorNodeProgressMessage


def pipeline_fixture(*, identity: str, task: PosthocPipelineType) -> Mock:
    pipeline = Mock(spec=PosthocPipeline)
    pipeline.id = identity
    pipeline.pipeline_type = task
    pipeline.recording_info = SimpleNamespace(recording_name="recording", full_recording_path="recording")
    return pipeline


def test_cancellation_scope_and_wrong_task_rejection() -> None:
    manager = PosthocPipelineManager(inference_service=Mock(spec=InferenceService),
        global_kill_flag=multiprocessing.Value("b", False),
        worker_registry=Mock(spec=WorkerRegistry),
    )
    mocap = pipeline_fixture(identity="motion", task=PosthocPipelineType.MOCAP)
    calibration = pipeline_fixture(identity="geometry", task=PosthocPipelineType.CALIBRATION)
    manager.pipelines = {mocap.id: mocap, calibration.id: calibration}
    realtime = Mock()
    sync = Mock()
    application = SimpleNamespace(posthoc_pipeline_manager=manager, realtime_pipeline_manager=realtime, sync_job_manager=sync)
    api = FastAPI()
    api.include_router(mocap_router)
    api.include_router(calibration_router)
    with patch("freemocap.api.http.mocap.mocap_router.get_freemocap_app", return_value=application), patch(
        "freemocap.api.http.calibration.calibration_router.get_freemocap_app", return_value=application
    ), TestClient(api) as client:
        assert client.delete("/mocap/realtime/pipelines").status_code == 200
        realtime.shutdown.assert_called_once()
        mocap.shutdown.assert_not_called()
        calibration.shutdown.assert_not_called()
        sync.shutdown.assert_not_called()
        assert client.delete("/mocap/posthoc/pipelines/geometry").status_code == 404
        assert set(manager.pipelines) == {"motion", "geometry"}
        assert client.delete("/mocap/posthoc/pipelines").status_code == 200
        mocap.shutdown.assert_called_once()
        calibration.shutdown.assert_not_called()
        assert set(manager.pipelines) == {"geometry"}
        assert client.delete("/calibration/posthoc/pipelines/geometry").status_code == 200
        calibration.shutdown.assert_called_once()
        assert not manager.pipelines
        assert not manager.global_kill_flag.value


def test_worker_crash_overrides_queued_completion() -> None:
    pipeline = pipeline_fixture(identity="motion", task=PosthocPipelineType.MOCAP)
    pipeline.video_nodes = {}
    pipeline.aggregation_node = Mock()
    pipeline.aggregation_node.worker.failure_exitcode = 17
    pipeline.aggregation_node.worker.name = "aggregation"
    pipeline.aggregation_node.get_progress_messages.return_value = [AggregatorNodeProgressMessage(
        pipeline_id="motion", pipeline_type="mocap", phase=AggregatorPhase.COMPLETE,
        progress_fraction=1.0, recording_name="recording", recording_path="recording",
    )]
    pipeline.queued_progress_message = None
    pipeline._latest_progress_by_id = {}
    pipeline.ipc = Mock()
    messages = PosthocPipeline.get_progress_messages(pipeline)
    assert len(messages) == 1
    assert messages[0].phase == AggregatorPhase.FAILED
    assert "17" in messages[0].detail
    pipeline.ipc.shutdown_pipeline.assert_called_once()
