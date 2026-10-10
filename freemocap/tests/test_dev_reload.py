"""Exercise real interpreter restart, logging and pub/sub without user jobs."""

import asyncio
import subprocess
import sys
import os
from pathlib import Path
from threading import Event, Thread
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from uvicorn import Server as UvicornServer

from freemocap.app.dev_reload import source_snapshot, supervise
from freemocap.app.serve_application import serve_application


def _probe_backend_logging():
    """Run real bootstrap in a fresh reload child, stopping before API/cameras."""
    import logging
    import freemocap.__main__ as entry
    from skellylogs import get_websocket_log_queue

    async def probe(*args, **kwargs):
        assert get_websocket_log_queue() is not None
        logger = logging.getLogger('reload_startup_regression')
        assert logging.getLogger().handlers
        relay = args[1]
        with relay.subscribe() as client:
            logger.info('Reload child logging initialized')
            record = await asyncio.to_thread(client.get, timeout=3)
            assert record['message'] == 'Reload child logging initialized'

    entry._run_application = probe
    asyncio.run(entry.main())


def test_real_logging_bootstrap_in_reload_child(tmp_path, monkeypatch):
    monkeypatch.setenv('SKELLYLOGS_LOG_DIR', str(tmp_path))
    child = subprocess.Popen([sys.executable, '-m',
        'freemocap.tests.test_dev_reload', 'logging'])
    try:
        assert child.wait(timeout=15) == 0
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


def _fake_backend(stop):
    from skellycam.core.ipc.pubsub.pubsub_manager import create_camera_group_pubsub_manager

    manager = create_camera_group_pubsub_manager('reload-regression')
    from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes

    subscription = manager.get_subscription(TopicTypes.LOGS)
    subscription.put('reload subscription works')
    assert subscription.get(timeout=3) == 'reload subscription works'
    manager.close()
    path = Path(os.environ['FREEMOCAP_RELOAD_TEST_LOG'])
    with path.open('a') as stream:
        stream.write(f'start {os.getpid()}\n')
    stop.wait(15)
    with path.open('a') as stream:
        stream.write(f'stop {os.getpid()}\n')


def test_restart_waits_for_shutdown_and_imports_fresh_process(tmp_path, monkeypatch):
    watched = tmp_path / 'source'
    watched.mkdir()
    source = watched / 'module.py'
    source.write_text('value = 1\n')
    log = tmp_path / 'lifecycle.txt'
    monkeypatch.setenv('FREEMOCAP_RELOAD_TEST_LOG', str(log))
    monkeypatch.setenv('SKELLYLOGS_LOG_DIR', str(tmp_path))
    stop = Event()
    observations = []

    def edit_then_stop():
        deadline = time.monotonic() + 15
        edited = False
        while time.monotonic() < deadline:
            lines = log.read_text().splitlines() if log.exists() else []
            if lines and not edited:
                source.write_text('value = 222\n')
                edited = True
            if len(lines) >= 3:
                observations.extend(lines)
                break
            time.sleep(0.05)
        stop.set()

    editor = Thread(target=edit_then_stop)
    editor.start()
    try:
        supervise(watched, command=[sys.executable, '-m',
            'freemocap.tests.test_dev_reload', 'lifecycle'],
            stop=stop, interval=0.05, debounce=0.1)
    finally:
        stop.set()
        editor.join()
    lines = log.read_text().splitlines()
    assert len(observations) == 3
    assert [line.split()[0] for line in lines] == ['start', 'stop', 'start', 'stop']
    assert lines[0].split()[1] == lines[1].split()[1]
    assert lines[2].split()[1] == lines[3].split()[1]
    assert lines[0].split()[1] != lines[2].split()[1]


def test_snapshot_detects_add_delete_and_ignores_output(tmp_path):
    before = source_snapshot(tmp_path)
    (tmp_path / 'output.csv').write_text('data')
    assert source_snapshot(tmp_path) == before
    source = tmp_path / 'new.py'
    source.write_text('x = 1')
    assert source_snapshot(tmp_path) != before
    source.unlink()
    assert source_snapshot(tmp_path) == before


@pytest.mark.asyncio
async def test_reload_requests_existing_graceful_shutdown():
    stop = Event()
    stop.set()

    class Server(UvicornServer):
        should_exit = False
        started = True

        def __init__(self):
            pass

        async def serve(self):
            while not self.should_exit:
                await asyncio.sleep(0)

    server = Server()
    app = FastAPI()
    app.state.global_kill_flag = SimpleNamespace(value=False)
    app.state.fatal_error = None
    await asyncio.wait_for(serve_application(server=server, app=app, reload_stop=stop), timeout=2)
    assert app.state.global_kill_flag.value
    assert server.should_exit


def test_packaged_launch_rejects_reload(monkeypatch):
    import freemocap.__main__ as entry

    monkeypatch.setattr(entry.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(entry.sys, 'argv', ['freemocap', '--reload'])
    monkeypatch.setattr(entry.multiprocessing, 'freeze_support', lambda: None)
    with pytest.raises(SystemExit) as error:
        entry.run_main()
    assert error.value.code == 2


if __name__ == '__main__':
    from freemocap.app.dev_reload import ShutdownFile

    if sys.argv[1] == 'logging':
        _probe_backend_logging()
    else:
        import freemocap.__main__ as entry

        async def probe(*args, **kwargs):
            _fake_backend(kwargs['reload_stop'])

        entry._run_application = probe
        asyncio.run(entry.main(reload_stop=ShutdownFile(Path(sys.argv[2]))))
