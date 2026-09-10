"""Task snapshots are replayable and independent of socket lifetimes."""

import multiprocessing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cbor2
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from freemocap.core.pipeline.inference_service import InferenceService

from freemocap.api.http.posthoc.tasks_router import tasks_router
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import (
    PosthocPipelineManager,
)
from freemocap.core.pipeline.posthoc.progress_messages import (
    AggregatorNodeProgressMessage,
    VideoNodeProgressMessage,
)
from freemocap.core.pipeline.posthoc.task_snapshot import (
    TaskRegistry,
    TaskRegistrySnapshot,
)
from freemocap.core.streaming.message_model import ProgressMessage, encode_message
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def test_recording_conversion_and_serialization_are_read_only(tmp_path: Path) -> None:
    recording = RecordingInfo(
        recording_directory=str(tmp_path), recording_name="absent"
    )
    registry = TaskRegistry()
    registry.register(
        task_id="parent:with:colons",
        task_type="calibration",
        recording=RecordingStructure.from_recording_info(recording=recording),
    )
    registry.update(
        task_id="parent:with:colons",
        messages=[
            VideoNodeProgressMessage(
                pipeline_id="opaque-node",
                camera_id="camera:identity",
                phase="processing_images",
                progress_fraction=0.5,
            )
        ],
    )
    snapshot = registry.snapshot()
    payload = cbor2.loads(encode_message(ProgressMessage(snapshot=snapshot)))
    decoded = TaskRegistrySnapshot.model_validate(payload["snapshot"])
    assert decoded == snapshot
    assert isinstance(decoded.tasks[0].recording.base_directory, Path)
    assert decoded.tasks[0].cameras[0].camera_id == "camera:identity"
    assert decoded.tasks[0].progress.progress_fraction is None
    assert not (tmp_path / "absent").exists()


def test_evicted_failure_remains_available_to_http_and_multiple_clients(
    tmp_path: Path,
) -> None:
    manager = PosthocPipelineManager(
        inference_service=Mock(spec=InferenceService),
        global_kill_flag=multiprocessing.Value("b", False),
        worker_registry=Mock(spec=WorkerRegistry),
    )
    manager.registry.register(
        task_id="task",
        task_type="calibration",
        recording=RecordingStructure(
            base_directory=tmp_path, recording_name="recording"
        ),
    )
    failure = AggregatorNodeProgressMessage(
        pipeline_id="task", phase="failed", detail="No usable board observations"
    )
    pipeline = Mock(started=True, alive=False)
    pipeline.get_progress_messages.return_value = [failure]
    pipeline.drain_and_get_messages.return_value = [failure]
    manager.pipelines["task"] = pipeline
    manager.access.reserve(recording=manager.registry.tasks["task"].recording, task_id="task")
    manager.refresh_progress()
    snapshot = manager.task_snapshot()
    assert not manager.pipelines and snapshot.tasks[0].status == "failed"
    assert manager.task_snapshot() == snapshot
    assert manager.task_snapshot() == snapshot
    pipeline.shutdown.assert_called_once()
    api = FastAPI()
    api.include_router(tasks_router)
    with (
        patch(
            "freemocap.api.http.posthoc.tasks_router.get_freemocap_app",
            return_value=SimpleNamespace(posthoc_pipeline_manager=manager),
        ),
        TestClient(api) as client,
    ):
        assert (
            TaskRegistrySnapshot.model_validate(client.get("/posthoc/tasks").json())
            == snapshot
        )


def test_terminal_history_is_bounded_without_pruning_running_tasks(
    tmp_path: Path,
) -> None:
    registry = TaskRegistry()
    recording = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    registry.register(task_id="running", task_type="mocap", recording=recording)
    for index in range(105):
        registry.register(
            task_id=str(index), task_type="calibration", recording=recording
        )
        registry.update(
            task_id=str(index),
            messages=[
                AggregatorNodeProgressMessage(
                    pipeline_id=str(index), phase="complete", progress_fraction=1.0
                )
            ],
        )
    registry.prune_completed(active_task_ids={"running"})
    assert len(registry.tasks) == 101
    assert "running" in registry.tasks and "0" not in registry.tasks


def test_repeated_progress_keeps_revision_and_detail_changes_advance_it(
    tmp_path: Path,
) -> None:
    registry = TaskRegistry()
    registry.register(
        task_id="task",
        task_type="mocap",
        recording=RecordingStructure(
            base_directory=tmp_path, recording_name="recording"
        ),
    )
    message = AggregatorNodeProgressMessage(
        pipeline_id="task", phase="triangulating", detail="first"
    )
    registry.update(task_id="task", messages=[message])
    before = registry.snapshot()
    registry.update(task_id="task", messages=[message])
    assert registry.snapshot() == before
    message.detail = "second"
    registry.update(task_id="task", messages=[message])
    assert registry.snapshot().revision > before.revision
    assert before.tasks[0].progress.detail == "first"
    assert TaskRegistry().server_instance_id != registry.server_instance_id
