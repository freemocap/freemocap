"""Selection, asynchronous export, retry, cancellation and automatic-run identity."""
from types import SimpleNamespace
from unittest.mock import Mock

from freemocap.core.recording.recording_access import RecordingAccess
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from freemocap.api.http.posthoc.exports_router import exports_router
from freemocap.api.http.posthoc import export_jobs
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.pipeline.posthoc.mocap_pipeline import complete_mocap, MocapWorkerRequest
from freemocap.core.recording.exports import wide_csv
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.tests.test_wide_csv_export import recording_processing  # noqa: F401


def test_api_selection_selected_run_stale_and_failed_retry(recording_processing, monkeypatch):
    structure, _ = recording_processing
    app = FastAPI()
    app.state.recording_access = RecordingAccess()
    app.include_router(exports_router)
    with TestClient(app) as client:
        preview = client.get('/exports/scientific', params=dict(recording_path=str(structure.full_path))).json()
        assert preview['formats'] == ['wide_csv', 'npy', 'npz', 'notebook']
        selected = preview['runs'][1]['channels'][0]['selection']
        body = dict(recording_path=str(structure.full_path), run_id=3, formats=['wide_csv'],
            expected_revision=preview['revision'], wide_csv=[selected])
        response = client.post('/exports/scientific', json=body)
        assert response.status_code == 202, response.text
        job = client.get('/exports/jobs/' + response.json()['job_id']).json()
        assert job['status'] == 'complete'
        assert len(job['result']['files']) == 1 and job['result']['run_id'] == 3
        assert client.post('/exports/scientific', json=dict(body, expected_revision='stale')).status_code == 409
        assert client.post('/exports/scientific', json=dict(body, wide_csv=[])).status_code == 422
        assert client.post('/exports/scientific', json=dict(body, formats=['unsupported'])).status_code == 422
        assert client.post('/exports/scientific', json=dict(body, wide_csv=[dict(selected, source='unknown')])).status_code == 409
        original = export_jobs.export_recording
        monkeypatch.setattr(export_jobs, 'export_recording', Mock(side_effect=OSError('Disk full')))
        failed = client.post('/exports/scientific', json=body).json()
        state = client.get('/exports/jobs/' + failed['job_id']).json()
        assert state['status'] == 'failed' and state['detail'] == 'Disk full'
        monkeypatch.setattr(export_jobs, 'export_recording', original)
        retry = client.post('/exports/scientific', json=body).json()
        assert client.get('/exports/jobs/' + retry['job_id']).json()['status'] == 'complete'


def test_job_cancellation_before_work(recording_processing):
    from freemocap.core.recording.exports.requests import ExportRequest
    structure, _ = recording_processing
    key = export_jobs.create_job()
    export_jobs.cancel_job(key)
    export_jobs.run_job(key, structure, ExportRequest(formats=('wide_csv',)))
    assert export_jobs.job_state(key)['status'] == 'cancelled'
    assert not structure.exports_dir.exists()


@pytest.mark.parametrize('stage', ['observations', 'filtering', 'reconstruction'])
@pytest.mark.parametrize('fails', [False, True])
def test_automatic_export_binds_produced_run_and_separates_failure(recording_processing, monkeypatch, stage, fails):
    structure, _ = recording_processing
    config = PosthocMocapPipelineConfig(startStage=stage, baseRunId=0, exportToBlender=False,
        exportOptions=dict(formats=['wide_csv']))
    reports, calls = [], []
    def writer(**kwargs):
        calls.append(kwargs['request'])
        if fails:
            raise OSError('Disk full')
        return SimpleNamespace(manifest_path=structure.exports_dir / 'metadata.json')
    monkeypatch.setattr(wide_csv, 'export_recording', writer)
    request = Mock(spec=MocapWorkerRequest, config=config, recording=SimpleNamespace(full_recording_path=structure.full_path),
        ipc=SimpleNamespace(should_continue=True), performance=PerformanceReport(), report=lambda *args: reports.append(args))
    before = structure.data_parquet_path.read_bytes()
    if fails:
        with pytest.raises(RuntimeError, match='requested exports incomplete'):
            complete_mocap(request)
        assert not any(r[0] == 'complete' for r in reports)
    else:
        complete_mocap(request)
        assert reports[-1][0] == 'complete'
    assert calls[0].run_id == 0  # selected run in the fixture is 3; the produced run is 0.
    assert calls[0].expected_revision
    assert structure.data_parquet_path.read_bytes() == before
