"""Exercise the saved-result HTTP boundary and post-processing export failures."""
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from freemocap.api.http.posthoc.exports_router import exports_router
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapWorkerRequest, complete_mocap
from freemocap.core.recording.exports import tall_csv
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.tests.test_saved_reconstruction import saved_request  # noqa: F401


def test_saved_result_export_and_stale_selection(saved_request):
    app = FastAPI()
    app.include_router(exports_router)
    with TestClient(app) as client:
        folder = str(saved_request.structure.full_path)
        before = saved_request.structure.data_parquet_path.read_bytes()
        preview = client.get('/exports/tall-csv', params={'recording_path': folder})
        assert preview.status_code == 200
        selection = preview.json()
        body = dict(recording_path=folder, run_id=selection['selected_run_id'],
                    expected_revision=selection['revision'])
        response = client.post('/exports/tall-csv', json=body)
        assert response.status_code == 200, response.text
        assert len(response.json()['files']) == 2
        assert saved_request.structure.data_parquet_path.read_bytes() == before
        body['expected_revision'] = 'stale'
        assert client.post('/exports/tall-csv', json=body).status_code == 409
        assert client.get('/exports/tall-csv', params={'recording_path': folder + '/missing'}).status_code == 404


@pytest.mark.parametrize('enabled,fails', [(True, False), (True, True), (False, False)])
def test_completion_exports_only_when_enabled_and_preserves_processing_success(saved_request, monkeypatch, enabled, fails):
    reports = []
    calls = []
    def export(**kwargs):
        calls.append(kwargs)
        if fails:
            raise OSError('Disk full')
        return SimpleNamespace(manifest_path=saved_request.structure.exports_dir / 'metadata.json')
    monkeypatch.setattr(tall_csv, 'export_tall_csv', export)
    request = Mock(spec=MocapWorkerRequest, config=PosthocMocapPipelineConfig(exportTallCsv=enabled),
        recording=SimpleNamespace(full_recording_path=saved_request.structure.full_path),
        ipc=SimpleNamespace(should_continue=True), report=lambda *args: reports.append(args))
    complete_mocap(request)
    assert len(calls) == int(enabled)
    assert reports[-1][0] == 'complete'
    assert ('tall CSV export failed: Disk full' in reports[-1][1]) == fails


def test_csv_default_and_alias():
    assert PosthocMocapPipelineConfig().export_tall_csv
    assert not PosthocMocapPipelineConfig(exportTallCsv=False).export_tall_csv
