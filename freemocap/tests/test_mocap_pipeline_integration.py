"""Managed graph lifecycle must preserve failure and cancellation reporting."""
import multiprocessing
import time
from queue import Queue
from unittest.mock import Mock

import pytest
from skellycam.core.ipc.process_management.managed_worker import ManagedWorker
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline, MocapWorkerRequest, run_mocap_pipeline
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


def make_request(tmp_path):
    ipc = PipelineIPC(pipeline_id="graph-test", ws_queue=multiprocessing.Queue(),
        global_kill_flag=multiprocessing.Value('b', False),
        heartbeat_timestamp=multiprocessing.Value('d', time.perf_counter()))
    return MocapWorkerRequest(pipeline_id="graph-test",
        recording=RecordingInfo(recording_name="recording", recording_directory=str(tmp_path)),
        config=PosthocMocapPipelineConfig(), ipc=ipc, progress_queue=Queue())


def test_worker_dispatches_only_application_graph(tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr('freemocap.core.pipeline.dataflow.application_pipeline.run_application_graph', run)
    request = make_request(tmp_path)
    run_mocap_pipeline(request=request)
    run.assert_called_once_with(request=request)


def test_graph_failure_stops_only_its_pipeline(tmp_path, monkeypatch):
    run = Mock(side_effect=RuntimeError('graph failure'))
    monkeypatch.setattr('freemocap.core.pipeline.dataflow.application_pipeline.run_application_graph', run)
    request = make_request(tmp_path)
    with pytest.raises(RuntimeError, match='graph failure'):
        run_mocap_pipeline(request=request)
    assert request.ipc.pipeline_shutdown_flag.value
    assert not request.ipc.global_kill_flag.value
    assert request.progress_queue.get_nowait().phase == AggregatorPhase.FAILED


def test_worker_exit_without_terminal_report_fails_pipeline(tmp_path):
    request = make_request(tmp_path)
    worker = Mock(spec=ManagedWorker)
    worker.is_alive.return_value = False
    worker.failure_exitcode = None
    worker.exitcode = 0
    pipeline = MocapPipeline(id=request.pipeline_id, recording_info=request.recording,
        ipc=request.ipc, worker=worker, progress_queue=request.progress_queue, started=True)
    pipeline._latest[pipeline.id] = Mock(phase=AggregatorPhase.SETTING_UP, operations=None, timing=None)
    assert pipeline.get_progress_messages()[-1].phase == AggregatorPhase.FAILED
    assert request.ipc.pipeline_shutdown_flag.value
