"""Every executor has retained, non-consuming HTTP and WebSocket task state."""
from types import SimpleNamespace
from unittest.mock import Mock
import multiprocessing

import cbor2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.process_management.managed_worker import WorkerMode

from freemocap.api.http.posthoc import export_jobs, tasks_router as routes
from freemocap.api import task_interface
from freemocap.api.websocket.websocket_server import WebsocketServer
from freemocap.core.pipeline.posthoc.sync_job_manager import SyncJobManager
from freemocap.core.pipeline.posthoc.task_snapshot import TaskProgress, TaskRegistry
from freemocap.core.recording.exports.requests import ExportRequest
from freemocap.core.tasks.background_task_state import BackgroundTaskState
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@pytest.fixture
def task_app(tmp_path, monkeypatch):
    registry = TaskRegistry()
    recording = RecordingStructure(base_directory=tmp_path, recording_name='clip')
    registry.register(task_id='processing', task_type='mocap', recording=recording)
    stop = Mock(side_effect=lambda *, pipeline_id, pipeline_type: registry.cancel(task_id=pipeline_id))
    kill_flag = multiprocessing.Value('b', False)
    sync = SyncJobManager(global_kill_flag=kill_flag,
                         worker_registry=WorkerRegistry(global_kill_flag=kill_flag, worker_mode=WorkerMode.THREAD))
    monkeypatch.setattr(export_jobs, '_jobs', {})
    monkeypatch.setattr(export_jobs, 'task_state', BackgroundTaskState())
    app = SimpleNamespace(posthoc_pipeline_manager=SimpleNamespace(task_snapshot=registry.snapshot, stop_pipeline=stop),
                          sync_job_manager=sync)
    monkeypatch.setattr(routes, 'get_freemocap_app', lambda: app)
    return app, recording


def api():
    app = FastAPI()
    app.include_router(routes.tasks_router)
    return app


def test_cancel_routes_preserve_scope_and_terminal_history(task_app):
    app, recording = task_app
    options = ExportRequest(formats=('wide_csv',), run_id=7, expected_revision='revision')
    key = export_jobs.create_job(structure=recording, request=options)
    with TestClient(api()) as client:
        first = client.get('/tasks').json()
        assert client.get('/tasks').json() == first
        exported = client.get(f'/tasks/export:{key}').json()
        assert exported['recording']['full_path'] == str(recording.full_path)
        assert (exported['source_run_id'], exported['source_revision']) == (7, 'revision')
        requested = client.post(f'/tasks/export:{key}/cancel').json()
        assert requested['cancellation_requested'] and requested['status'] == 'queued'
        app.posthoc_pipeline_manager.stop_pipeline.assert_not_called()
        export_jobs.run_job(key, recording, options)
        terminal = client.get(f'/tasks/export:{key}').json()
        assert terminal['status'] == 'cancelled'
        assert client.post(f'/tasks/export:{key}/cancel').json() == terminal
        assert client.post('/tasks/cancel', json={'kind': 'calibration'}).status_code == 200
        app.posthoc_pipeline_manager.stop_pipeline.assert_not_called()
        assert client.post('/tasks/processing/cancel').json()['status'] == 'cancelled'
        app.posthoc_pipeline_manager.stop_pipeline.assert_called_once_with(pipeline_id='processing', pipeline_type='mocap')
        assert client.get('/tasks/absent').status_code == 404
        assert client.post('/tasks/absent/cancel').status_code == 404


def test_sync_progress_and_result_survive_cleanup_and_client_reconnect(task_app):
    app, _ = task_app
    manager = app.sync_job_manager
    from freemocap.core.pipeline.posthoc.progress_messages import SyncJobProgressMessage
    job = SimpleNamespace(id='one', started=False, is_alive=False, queued_message=None,
        get_progress_messages=Mock(return_value=[SyncJobProgressMessage(phase='complete', progress_fraction=1.0)]),
        finished=False, result=None, error=None)
    manager.jobs[job.id] = job
    manager.task_state.register('sync:one', 'sync')
    manager.refresh_progress()
    assert manager.task_state.snapshot()[1][0].status == 'running', 'Completion needs the actual result'
    job.finished = True
    job.result = SimpleNamespace(model_dump=lambda **kwargs: {'synchronized_frame_count': 48})
    manager.refresh_progress()
    manager.cleanup_job(job.id)
    assert manager.get_job(job.id) is None
    with TestClient(api()) as client:
        first = client.get('/tasks/sync:one').json()
    with TestClient(api()) as reconnected:
        assert reconnected.get('/tasks/sync:one').json() == first
    assert first['status'] == 'complete' and first['result']['synchronized_frame_count'] == 48
    assert first['recording'] is None, 'External videos need no destination recording yet'


def test_sync_cancellation_retains_state_after_worker_removal(task_app):
    app, _ = task_app
    manager = app.sync_job_manager
    job = SimpleNamespace(id='one', started=False, is_alive=False, queued_message=None,
        get_progress_messages=lambda: [], finished=False, shutdown=Mock())
    manager.jobs[job.id] = job
    manager.task_state.register('sync:one', 'sync')
    task = task_interface.cancel_task(app, 'sync:one')
    assert task.status == 'cancelled' and manager.get_job(job.id) is None
    job.shutdown.assert_called_once()
    assert task_interface.cancel_task(app, 'sync:one') == task


async def test_http_and_each_websocket_send_the_same_snapshot(task_app):
    app, _ = task_app
    export_jobs.create_job()
    app.sync_job_manager.task_state.register('sync:one', 'sync')
    with TestClient(api()) as client:
        expected = client.get('/tasks').json()
    for _ in range(2):
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
        assert sent[0]['snapshot'] == expected


def test_bounded_background_history_preserves_active_and_terminal_results():
    state = BackgroundTaskState(completed_limit=2)
    state.register('active', 'export')
    for index in range(4):
        key = str(index)
        state.register(key, 'sync')
        state.update(key, status='complete', result={'frames': index},
                     progress=TaskProgress(phase='complete', progress_fraction=1, detail='Done'))
    before = state.snapshot()
    assert {task.task_id for task in before[1]} == {'active', '2', '3'}
    state.update('3', status='failed', error='Late observation')
    state.update('0', status='running')  # An evicted terminal executor cannot resurrect itself.
    assert state.snapshot() == before
