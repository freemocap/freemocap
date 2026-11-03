"""Realtime operations use retained PROGRESS tasks without HTTP status polling."""
from types import SimpleNamespace
from unittest.mock import Mock

import cbor2
import pytest
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.api import task_interface
from freemocap.api.http.posthoc import export_jobs
from freemocap.api.websocket.websocket_server import WebsocketServer
from freemocap.core.pipeline.inference_service import InferenceClient, InferenceRegistration, InferenceService
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistry
from freemocap.core.pipeline.realtime.startup_status import RealtimeStartupStatus
from freemocap.core.tasks.background_task_state import BackgroundTaskState


@pytest.fixture
def owners(monkeypatch):
    service = InferenceService(worker_registry=Mock(spec=WorkerRegistry))
    registration = Mock(spec=InferenceRegistration, pipeline_id="live", shutdown_flag=SimpleNamespace(value=False))
    client = InferenceClient(registration=registration, _service=service)
    client._active_provider = "cuda"
    service._clients.append(client)
    registry = TaskRegistry()
    monkeypatch.setattr(export_jobs, 'task_state', BackgroundTaskState())
    app = SimpleNamespace(startup_status=RealtimeStartupStatus(), inference_service=service,
        posthoc_pipeline_manager=SimpleNamespace(task_snapshot=registry.snapshot, stop_pipeline=Mock()),
        sync_job_manager=SimpleNamespace(task_state=BackgroundTaskState()))
    return app, service, client


async def delivered_progress(app):
    server = WebsocketServer.__new__(WebsocketServer)
    server._app = app
    server._global_kill_flag = SimpleNamespace(value=False)
    server._websocket_should_continue = True
    sent = []

    async def send(payload):
        sent.append(cbor2.loads(payload))
        server._websocket_should_continue = False

    server._serializer = SimpleNamespace(is_connected=True, send_message=send)
    await server._posthoc_progress_sender()
    return sent[0]['snapshot']


async def test_progress_sender_merges_startup_inference_without_http_and_replays_terminal(owners):
    app, service, client = owners
    app.startup_status.begin()
    app.startup_status.pipeline_created('live')
    service._record_startup(client, 'warming_models', 'Warming pose')
    warming = await delivered_progress(app)
    task = next(task for task in warming['tasks'] if task['task_type'] == 'realtime_startup')
    assert task['result']['phase'] == 'warming_models' and task['status'] == 'running'
    app.startup_status.record_preview_delivery()
    service._record_startup(client, 'running', 'Ready')
    waiting = task_interface.task_snapshot(app).tasks[0]
    assert waiting.result['phase'] == 'waiting_for_frames' and waiting.result['preview_ready']
    app.startup_status.record_frame_delivery('live')
    complete = await delivered_progress(app)
    reconnected = await delivered_progress(app)
    assert complete == reconnected
    assert complete['tasks'][0]['status'] == 'complete'
    app.startup_status.begin()
    tasks = task_interface.task_snapshot(app).tasks
    assert len(tasks) == 2 and tasks[0].status == 'complete' and tasks[1].status == 'running'
    assert tasks[0].task_id != tasks[1].task_id
