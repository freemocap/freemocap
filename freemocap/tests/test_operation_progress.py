"""Concurrent operations survive queue coalescing and WebSocket reconnects."""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock

import cbor2

from freemocap.core.pipeline.posthoc.operation_progress import OperationProgressReporter
from freemocap.core.pipeline.posthoc.progress_messages import AggregatorNodeProgressMessage
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistry, TaskRegistrySnapshot
from freemocap.core.streaming.message_model import ProgressMessage, encode_message
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def test_coalesced_snapshot_contains_all_concurrent_operations(tmp_path):
    reporter = OperationProgressReporter()
    request = SimpleNamespace(pipeline_id="run", progress_queue=Queue(),
        recording=SimpleNamespace(recording_name="recording", full_recording_path=tmp_path))

    def run_operation(index):
        reporter.update(request, str(index), f"Export {index}", "running", completed=1, total=2, unit="channels")
        reporter.update(request, str(index), f"Export {index}", "complete", completed=2, total=2, unit="channels")

    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(run_operation, range(12)))
    reporter.report(request, "complete", "All requested exports saved", 1.0)
    messages = list(request.progress_queue.queue)
    counts = [len(message.operations) for message in messages]
    assert counts == sorted(counts)
    latest = messages[-1]
    assert len(latest.operations) == 12
    assert all(operation.status == "complete" for operation in latest.operations)
    registry = TaskRegistry()
    registry.register(task_id="run", task_type="mocap",
        recording=RecordingStructure(base_directory=tmp_path, recording_name="recording"))
    registry.update(task_id="run", messages=[latest])
    decoded = TaskRegistrySnapshot.model_validate(cbor2.loads(encode_message(
        ProgressMessage(snapshot=registry.snapshot())))["snapshot"])
    assert decoded.tasks[0].operations == latest.operations
    assert decoded.tasks[0].status == "complete"


def test_legacy_terminal_message_retains_operations_and_cancel_marks_active(tmp_path):
    reporter = OperationProgressReporter()
    request = SimpleNamespace(pipeline_id="run", progress_queue=Queue(),
        recording=SimpleNamespace(recording_name="recording", full_recording_path=tmp_path))
    reporter.update(request, "csv", "Save CSV", "complete")
    reporter.update(request, "blender", "Create Blender scene", "running")
    registry = TaskRegistry()
    registry.register(task_id="run", task_type="mocap",
        recording=RecordingStructure(base_directory=tmp_path, recording_name="recording"))
    registry.update(task_id="run", messages=list(request.progress_queue.queue))
    registry.update(task_id="run", messages=[AggregatorNodeProgressMessage(
        pipeline_id="run", phase="exporting_blender", detail="Waiting for Blender")])
    assert len(registry.tasks["run"].operations) == 2
    registry.cancel(task_id="run")
    assert [operation.status for operation in registry.tasks["run"].operations] == ["complete", "cancelled"]


def test_completion_sets_full_count_without_erasing_other_operation(tmp_path):
    reporter = OperationProgressReporter()
    request = SimpleNamespace(pipeline_id="run", progress_queue=Queue(),
        recording=SimpleNamespace(recording_name="recording", full_recording_path=tmp_path))
    reporter.update(request, "csv", "Save CSV", "running", completed=2, total=3, unit="channels")
    reporter.update(request, "blender", "Create Blender scene", "running")
    reporter.update(request, "csv", "Save CSV", "complete", "Saved and validated")
    latest = list(request.progress_queue.queue)[-1]
    csv, blender = latest.operations
    assert (csv.progress_fraction, csv.completed, csv.total) == (1.0, 3, 3)
    assert blender.status == "running"
    assert blender.progress_fraction is None


def test_worker_exit_retains_last_queued_operation_snapshot(tmp_path):
    from skellycam.core.ipc.process_management.managed_worker import ManagedWorker
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
    from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline

    reporter = OperationProgressReporter()
    queue = Queue()
    recording = RecordingInfo(recording_directory=str(tmp_path), recording_name="recording")
    request = SimpleNamespace(pipeline_id="run", progress_queue=queue, recording=recording)
    reporter.update(request, "csv", "Save CSV", "complete")
    reporter.update(request, "blender", "Create Blender scene", "failed", "Blender exited")
    worker = Mock(spec=ManagedWorker, failure_exitcode=1, exitcode=1)
    worker.is_alive.return_value = False
    pipeline = MocapPipeline(id="run", recording_info=recording,
        ipc=Mock(spec=PipelineIPC), worker=worker, progress_queue=queue, started=True)
    message, = pipeline.get_progress_messages()
    assert message.phase == "failed"
    assert [operation.status for operation in message.operations] == ["complete", "failed"]


def test_server_reports_independent_durations_per_motion_frame(tmp_path, monkeypatch):
    from freemocap.core.pipeline.posthoc import operation_progress
    from freemocap.core.pipeline.performance_report import PerformanceReport

    clock = [100.0]
    monkeypatch.setattr(operation_progress, "perf_counter", lambda: clock[0])
    performance = Mock(spec=PerformanceReport, frames=222, images=666, elapsed_seconds=62.919)
    reporter = OperationProgressReporter()
    request = SimpleNamespace(pipeline_id="run", progress_queue=Queue(), performance=performance,
        recording=SimpleNamespace(recording_name="recording", full_recording_path=tmp_path))
    reporter.update(request, "science", "Calculate skeleton motion", "running")
    clock[0] = 105.0
    reporter.update(request, "annotation", "Save annotated video", "running")
    clock[0] = 110.0
    reporter.update(request, "science", "Calculate skeleton motion", "complete")
    clock[0] = 112.0
    reporter.update(request, "annotation", "Save annotated video", "complete")
    reporter.report(request, "complete", "Saved", 1.0)
    latest = list(request.progress_queue.queue)[-1]
    assert [operation.elapsed_seconds for operation in latest.operations] == [10.0, 7.0]
    assert latest.operations[0].seconds_per_motion_frame == 10.0 / 222
    assert latest.operations[1].seconds_per_motion_frame == 7.0 / 222
    assert latest.timing.elapsed_seconds == 62.919
    assert latest.timing.motion_frame_count == 222
    assert latest.timing.seconds_per_motion_frame == 62.919 / 222
    registry = TaskRegistry()
    registry.register(task_id="run", task_type="mocap",
        recording=RecordingStructure(base_directory=tmp_path, recording_name="recording"))
    registry.update(task_id="run", messages=[latest])
    decoded = TaskRegistrySnapshot.model_validate(cbor2.loads(encode_message(
        ProgressMessage(snapshot=registry.snapshot())))["snapshot"])
    assert decoded.tasks[0].timing == latest.timing
    assert decoded.tasks[0].operations == latest.operations


def test_unknown_frame_count_never_becomes_camera_image_denominator(tmp_path, monkeypatch):
    from freemocap.core.pipeline.posthoc import operation_progress
    from freemocap.core.pipeline.performance_report import PerformanceReport

    clock = [0.0]
    monkeypatch.setattr(operation_progress, "perf_counter", lambda: clock[0])
    request = SimpleNamespace(pipeline_id="run", progress_queue=Queue(),
        performance=Mock(spec=PerformanceReport, frames=0, images=666, elapsed_seconds=5.0),
        recording=SimpleNamespace(recording_name="recording", full_recording_path=tmp_path))
    reporter = OperationProgressReporter()
    reporter.update(request, "export", "Save exports", "running")
    clock[0] = 5.0
    reporter.update(request, "export", "Save exports", "complete")
    reporter.report(request, "complete", "Saved", 1.0)
    latest = list(request.progress_queue.queue)[-1]
    assert latest.operations[0].elapsed_seconds == 5.0
    assert latest.operations[0].seconds_per_motion_frame is None
    assert latest.timing.motion_frame_count is None
    assert latest.timing.seconds_per_motion_frame is None
