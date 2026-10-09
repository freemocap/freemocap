"""Missing, stale and incomplete outputs cannot certify a reference run."""
from pathlib import Path

import pytest

from freemocap.core.recording.exports.publication import digest
from freemocap.tools.datasets.output_acceptance import accept_outputs, verify_outputs


@pytest.fixture
def accepted(tmp_path):
    recording = tmp_path / 'recording'
    recording.mkdir()
    parquet = recording / 'recording_data.parquet'
    parquet.write_bytes(b'canonical result')
    (recording / 'recording.blend').write_bytes(b'saved scene')
    validation = dict(parquet_sha256=digest(parquet), run_id=0, sensor_group='cameras', frames=3, rows=9)
    report = accept_outputs(recording, validation, profile='standard', blender_checks={'frames': 3})
    return recording, report


def test_valid_artifacts_survive_recording_relocation(accepted, tmp_path):
    recording, report = accepted
    destination = tmp_path / 'moved'
    recording.rename(destination)
    assert verify_outputs(destination, report).profile == 'standard'


@pytest.mark.parametrize('kind', ['parquet', 'blender'])
def test_changed_artifact_cannot_pass(accepted, kind):
    recording, report = accepted
    (recording / report['outputs']['artifacts'][kind]['path']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='missing or changed'):
        verify_outputs(recording, report)


@pytest.mark.parametrize('mutation', ['missing', 'failed', 'source', 'revision', 'run', 'group', 'required', 'escape'])
def test_incomplete_or_misbound_reports_fail(accepted, mutation):
    recording, report = accepted
    artifact = report['outputs']['artifacts']['blender']
    if mutation == 'missing':
        del report['outputs']['artifacts']['blender']
    elif mutation == 'failed':
        artifact['status'] = 'failed'
    elif mutation == 'source':
        artifact['source_sha256'] = 'old source'
    elif mutation == 'revision':
        artifact['source_revision'] = 'old revision'
    elif mutation == 'run':
        artifact['run_id'] = 1
    elif mutation == 'group':
        artifact['sensor_group'] = 'different camera group'
    elif mutation == 'required':
        report['outputs']['required'] = ['parquet']
    else:
        artifact['path'] = '../outside.blend'
    with pytest.raises(ValueError):
        verify_outputs(recording, report)


def test_numerical_scope_is_explicit(accepted):
    recording, validation = accepted
    report = accept_outputs(recording, validation, profile='numerical')
    assert verify_outputs(recording, report, require_complete=False).profile == 'numerical'
    with pytest.raises(ValueError, match='Numerical-only'):
        verify_outputs(recording, report)


def test_generation_without_content_validation_cannot_pass(accepted):
    recording, validation = accepted
    with pytest.raises(ValueError, match='Missing content validation'):
        accept_outputs(recording, validation, profile='standard')


def test_missing_blender_stops_worker_before_inference(tmp_path, monkeypatch):
    import json
    from unittest.mock import Mock
    from freemocap.tools.datasets import blender_validation, preparation
    from freemocap.core.pipeline import inference_service
    request = tmp_path / 'request.json'
    request.write_text(json.dumps(dict(recording=str(tmp_path / 'recording'), output_profile='standard')))
    monkeypatch.setenv('FREEMOCAP_BASE_FOLDER', str(tmp_path / 'app-data'))
    monkeypatch.setattr(blender_validation, 'preflight_blender', Mock(side_effect=RuntimeError('Blender missing')))
    inference = Mock(side_effect=AssertionError('Inference started before Blender preflight'))
    monkeypatch.setattr(inference_service, 'InferenceService', inference)
    with pytest.raises(RuntimeError, match='Blender missing'):
        preparation.run_worker(request)
    inference.assert_not_called()
    assert not (tmp_path / 'result.json').exists()
