"""Enter the full-processing branch with the application's beartype hook active."""
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.pipeline.posthoc import mocap_pipeline
from freemocap.core.pipeline.posthoc.mocap_detection import MocapDetectionFrame
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


def test_full_processing_reaches_detection_and_numerical_work(monkeypatch, tmp_path):
    # Importing freemocap activates beartype's AST hook, including local variable
    # annotations. Mock only expensive work; execute the real coordinator body.
    assert hasattr(mocap_pipeline.run_mocap_pipeline, '__wrapped__')
    def frames(request):
        yield MocapDetectionFrame(frame_number=0, frame_count=1, observations={},
            selected_board=None, video_metadata={})
    detector = Mock(side_effect=frames)
    numerical, complete = Mock(), Mock()
    monkeypatch.setattr(mocap_pipeline, 'detect_mocap_recording', detector)
    monkeypatch.setattr(mocap_pipeline, 'run_posthoc_mocap_task', numerical)
    monkeypatch.setattr(mocap_pipeline, 'complete_mocap', complete)
    ipc = Mock(spec=PipelineIPC, should_continue=True)
    request = Mock(spec=mocap_pipeline.MocapWorkerRequest,
        pipeline_id='runtime-regression', config=PosthocMocapPipelineConfig(),
        recording=SimpleNamespace(full_recording_path=tmp_path), ipc=ipc,
        progress_queue=Queue(), registry=Mock(spec=WorkerRegistry),
        inference_service=Mock(spec=InferenceService), video_nodes=[],
        performance=PerformanceReport())
    mocap_pipeline.run_mocap_pipeline(request=request)
    detector.assert_called_once()
    assert numerical.call_args.kwargs['frame_observations'] == [{}]
    complete.assert_called_once_with(request)
    ipc.shutdown_pipeline.assert_not_called()
