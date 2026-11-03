"""Realtime operations use retained PROGRESS tasks without HTTP status polling."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import cbor2
import pytest
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core.sessions.onnx_preparation import PreparationPhase

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
    client._startup_ready = client._preparation_supported = True
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


def fake_job(phase, *, alive=False):
    state = SimpleNamespace(phase=phase, elapsed_seconds=1.0, reason=None)
    native = SimpleNamespace(phase='warming_models', model_name='pose', alive=alive)
    return SimpleNamespace(snapshot=lambda: state, runtime=SimpleNamespace(status=lambda: native),
                           state=state, native=native)


def test_preparation_ready_waits_for_activation_and_retry_gets_new_retained_task(owners):
    app, service, client = owners
    assert not task_interface.task_snapshot(app).tasks
    service.request_preparation('live')
    first_id = client._preparation_task_id
    client._preparation_intent = None
    client._preparation_job = fake_job(PreparationPhase.READY, alive=True)
    ready = task_interface.find_task(app, first_id)
    assert ready.status == 'running' and ready.result['status'] == 'ready'
    client._active_provider = 'trt'
    activated = task_interface.find_task(app, first_id)
    assert activated.status == 'complete' and activated.result['active_provider'] == 'trt'
    assert activated.result['status'] == 'activated'

    # A new CUDA client/pipeline generation may prepare again, never overwrite history.
    client._active_provider = 'cuda'
    client._preparation_job = None
    service.request_preparation('live')
    second_id = client._preparation_task_id
    assert second_id != first_id
    client._preparation_intent = None
    client._preparation_job = fake_job(PreparationPhase.FAILED)
    failed = task_interface.find_task(app, second_id)
    assert failed.status == 'failed'
    service.request_preparation('live')
    assert client._preparation_task_id not in (first_id, second_id)
    assert task_interface.find_task(app, first_id) == activated
    assert task_interface.find_task(app, second_id) == failed


async def test_cancellation_routes_to_owners_and_retains_cleanup_until_done(owners):
    app, service, client = owners
    app.startup_status.begin()

    async def stop_startup():
        app.startup_status.request_stop()

    app.stop_realtime_startup = AsyncMock(side_effect=stop_startup)
    task = await task_interface.cancel_task_async(app, app.startup_status.task_id)
    assert task.status == 'running' and task.result['status'] == 'stopping'
    app.startup_status.stopped()
    assert task_interface.find_task(app, task.task_id).status == 'cancelled'
    app.posthoc_pipeline_manager.stop_pipeline.assert_not_called()

    service.request_preparation('live')
    task_id = client._preparation_task_id
    stopping = await task_interface.cancel_task_async(app, task_id)
    assert stopping.result['status'] == 'stopping'
    client._preparation_job = fake_job(PreparationPhase.CANCELLED, alive=True)
    service.release(client=client)
    service._clients.remove(client)
    cleaning = task_interface.find_task(app, task_id)
    assert cleaning.status == 'running'
    assert not cleaning.result['can_prepare'] and not cleaning.result['can_cancel']
    client._preparation_job.native.alive = False
    terminal = task_interface.find_task(app, task_id)
    assert terminal.status == 'cancelled'
    assert not terminal.result['can_prepare'] and not terminal.result['can_cancel']
    assert task_interface.find_task(app, task_id) == terminal


async def test_preparation_terminal_and_retry_replay_on_existing_websocket_without_native_work(owners, monkeypatch):
    from skellytracker.core.sessions.onnx_session import OnnxSession
    construct = Mock(side_effect=AssertionError('Progress must not construct a native session'))
    monkeypatch.setattr(OnnxSession, 'create', construct)
    app, service, client = owners
    service.request_preparation('live')
    first_id = client._preparation_task_id
    client._preparation_intent = None
    client._preparation_job = fake_job(PreparationPhase.CANCELLED)
    first = await delivered_progress(app)
    assert first['tasks'][0]['task_id'] == first_id and first['tasks'][0]['status'] == 'cancelled'
    assert await delivered_progress(app) == first
    service.request_preparation('live')
    second = await delivered_progress(app)
    assert second['tasks'][0] == first['tasks'][0]
    assert second['tasks'][1]['task_id'] != first_id and second['tasks'][1]['status'] == 'queued'
    construct.assert_not_called()


def test_inference_transition_publication_does_not_copy_history_or_tick_every_frame(owners):
    _, service, client = owners
    service.request_preparation('live')
    client._preparation_intent = None
    client._preparation_job = fake_job(PreparationPhase.BUILDING, alive=True)
    with service._condition:
        service._publish_preparation_tasks_locked()
        revision = service.preparation_task_state.revision
        client._preparation_job.state.elapsed_seconds = 2.0
        service._publish_preparation_tasks_locked()
    assert service.preparation_task_state.revision == revision
    service.preparation_tasks_snapshot()
    assert service.preparation_task_state.revision == revision + 1


def test_closed_before_preparation_execution_is_retained_cancelled(owners):
    app, service, client = owners
    service.request_preparation('live')
    service.release(client=client)
    service._clients.remove(client)
    task = task_interface.find_task(app, client._preparation_task_id)
    assert task.status == 'cancelled' and not task.result['can_cancel']
