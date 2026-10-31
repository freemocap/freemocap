"""Exercise production server ownership without opening physical cameras."""
import json
from pathlib import Path

from fastapi import APIRouter, FastAPI
import pytest

from freemocap.api.route_inventory import write_route_inventory
from freemocap.tools.hardware_validation.server_session import ApiResponseError, ServerSession
from freemocap.tools.hardware_validation.stream_client import StreamClient


def test_inventory_includes_nested_hidden_and_websocket_routes(tmp_path: Path):
    app = FastAPI()
    router = APIRouter(prefix='/nested')

    @router.get('/hidden', include_in_schema=False)
    async def hidden_route():
        return {}

    @router.websocket('/frames')
    async def frame_route(websocket):
        pass

    app.include_router(router, prefix='/outer')
    output_path = tmp_path / 'inventory.json'
    write_route_inventory(app, str(output_path))
    inventory = {entry['path']: entry for entry in json.loads(output_path.read_text())}
    assert inventory['/outer/nested/hidden']['methods'] == ['GET']
    assert not inventory['/outer/nested/hidden']['in_openapi']
    assert inventory['/outer/nested/frames']['methods'] == ['WEBSOCKET']


def test_server_cleanup_after_client_failure(tmp_path: Path):
    session = ServerSession(tmp_path / 'server')
    with pytest.raises(RuntimeError, match='deliberate client failure') as failure:
        with session:
            with StreamClient(session.api_client.server_url) as stream:
                assert stream.wait_for_state()['camera_groups'] == {}
                assert stream.socket.response.headers.get('Sec-WebSocket-Extensions') is None
            with pytest.raises(ApiResponseError) as captured:
                session.api_client.request('GET', '/nonexistent-harness-route')
            assert captured.value.status_code == 404
            raise RuntimeError('deliberate client failure')
    assert session.process.poll() is not None
    cleanup_report = json.loads((session.output_directory / 'server-cleanup.json').read_text())
    assert cleanup_report['exit_code'] == session.process.returncode
    if session.process.returncode != 0:
        assert f'Server exit code: {session.process.returncode}' in cleanup_report['errors']
        assert any('Server exit code:' in note for note in failure.value.__notes__)
    with pytest.raises(FileExistsError):
        with ServerSession(session.output_directory):
            pass


def test_existing_hardware_reports_are_not_overwritten(tmp_path: Path):
    from freemocap.tools.hardware_validation.hardware_run import run_baseline
    from freemocap.tools.hardware_validation.suite_runner import run_suite
    (tmp_path / 'baseline.json').write_text('original baseline', encoding='utf-8')
    (tmp_path / 'suite-report.json').write_text('original suite', encoding='utf-8')
    assert run_baseline(tmp_path, 'python')['status'] == 'failed'
    assert not run_suite(tmp_path, 'python', 'quick')['passed']
    assert (tmp_path / 'baseline.json').read_text(encoding='utf-8') == 'original baseline'
    assert (tmp_path / 'suite-report.json').read_text(encoding='utf-8') == 'original suite'
