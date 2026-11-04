import copy
import json
from pathlib import Path

import pytest

from freemocap.tools.machine_benchmarks import collect_camera, collect_dataset, compare, portable


def record(label, workload, value, status='passed'):
    return dict(schema_version=1, machine=dict(label=label), conditions='shared desktop', provenance={},
                cases=[dict(workload=workload, status=status, metrics={'worker_elapsed_s': value})])


def test_comparison_groups_only_matching_work_and_excludes_failed_timings():
    work = dict(kind='dataset', dataset='test_data', output_profile='numerical', videos=[{'sha256': 'one'}])
    other = copy.deepcopy(work)
    other['videos'][0]['sha256'] = 'different input'
    result = compare([record('mac', work, 4), record('mac', work, 6), record('win', work, 10),
                      record('mac', work, 100, 'failed'), record('mac', other, 2)])
    assert len(result['groups']) == 2
    stats = result['groups'][0]['successful_run_statistics']
    assert stats['mac']['worker_elapsed_s']['n'] == 2
    assert stats['mac']['worker_elapsed_s']['median'] == 5
    assert stats['win']['worker_elapsed_s']['ratio_to_first_successful_machine'] == 2
    assert len(result['groups'][0]['measurements']) == 4


def test_missing_metrics_and_zero_baseline_are_not_invented():
    source = record('mac', {'kind': 'camera'}, 0)
    other = record('win', {'kind': 'camera'}, 5)
    result = compare([source, other])
    assert result['groups'][0]['successful_run_statistics']['win']['worker_elapsed_s']['ratio_to_first_successful_machine'] is None
    with pytest.raises(ValueError, match='schema'):
        compare([dict(source, schema_version=99)])


def test_missing_dataset_readiness_is_failure_even_if_worker_completed(tmp_path):
    attempt = tmp_path / 'prepared/freemocap_test_data/attempts/one'
    attempt.mkdir(parents=True)
    (attempt / 'performance.json').write_text(json.dumps(dict(status='complete', elapsed_s=10)))
    result = collect_dataset(tmp_path, 'test_data', 'numerical', 'rtmpose')
    assert result['status'] == 'failed'
    assert result['metrics'] == {'worker_elapsed_s': 10}


def camera_report(root, identity, count=1):
    folder = root / 'python'
    folder.mkdir(parents=True)
    identities = [identity] if count == 1 else [identity, 'second']
    (folder / 'camera-inventory.json').write_text(json.dumps([dict(camera_id=identity, name='physical model')]))
    (folder / 'suite-report.json').write_text(json.dumps(dict(server_errors=[], cases=[dict(
        case=dict(case_name=f'record-{identity}', control_name='', camera_ids=identities, requested_ids=[]),
        status='passed', elapsed_seconds=6, recordings=[dict(cameras={identity: dict(measured_fps=29.9)})]) ])))


def test_camera_identity_is_context_but_count_is_comparison_boundary(tmp_path):
    camera_report(tmp_path / 'a', 'abcd')
    camera_report(tmp_path / 'b', 'efgh')
    camera_report(tmp_path / 'c', 'ijkl', 2)
    first, second, third = [collect_camera(tmp_path / name, 'python')[0] for name in ('a', 'b', 'c')]
    assert first['workload'] == second['workload']
    assert first['metrics'] == second['metrics']
    assert first['workload'] != third['workload']
    assert first['camera_inventory'] != second['camera_inventory']


def test_suite_startup_failure_is_retained(tmp_path):
    folder = tmp_path / 'rust'
    folder.mkdir()
    (folder / 'suite-report.json').write_text(json.dumps(dict(cases=[], server_errors=['No cameras'])))
    result = collect_camera(tmp_path, 'rust')[0]
    assert result['status'] == 'failed'
    assert result['error'] == ['No cameras']
    assert result['metrics'] == {}


def test_published_records_replace_home_in_nested_paths():
    assert portable({'items': [str(Path.home() / 'private/run')]}) == {'items': ['<HOME>/private/run']}


def test_wrapper_delegates_to_existing_runner_and_persists_failure(tmp_path, monkeypatch):
    from argparse import Namespace
    from subprocess import CompletedProcess
    from freemocap.tools import machine_benchmarks as module
    machine = dict(label='test', cpu='test CPU', memory_bytes=1024)
    monkeypatch.setattr(module, 'machine_info', lambda label: machine)
    monkeypatch.setattr(module, 'capture_provenance', lambda: {})
    monkeypatch.setattr(module, 'load_snapshot', lambda: {})
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 1)
    monkeypatch.setattr(module.subprocess, 'run', execute)
    args = Namespace(command='dataset', output=tmp_path / 'new', machine='test', conditions='unit test',
                     dataset='test_data', recordings_root=tmp_path / 'raw', output_profile='numerical',
                     tracker_preset='rtmpose', timeout=30, blender_path=None)
    assert module.run(args) == 1
    assert calls[0][2:6] == ['-m', 'freemocap.tools.datasets', 'process', 'test_data']
    saved = json.loads((args.output / 'benchmark.json').read_text())
    assert saved['status'] == 'failed'
    assert saved['cases'][0]['metrics'] == {}
    assert (args.output / 'benchmark.md').exists()
    with pytest.raises(FileExistsError):
        module.run(args)
    assert len(calls) == 1


def test_archive_only_publishes_completed_small_records_and_never_overwrites(tmp_path):
    from freemocap.tools.machine_benchmarks import archive
    source = tmp_path / 'source'
    source.mkdir()
    original = record('mac', {'kind': 'dataset'}, 2)
    original.update(status='running', started_utc='2026-11-03T00:00:00Z')
    original['machine'].update(cpu='CPU', memory_bytes=1024)
    (source / 'benchmark.json').write_text(json.dumps(original))
    (source / 'private-video.mp4').write_bytes(b'not published')
    destination = tmp_path / 'results' / 'one'
    with pytest.raises(ValueError, match='completed'):
        archive(source, destination)
    original['status'] = 'passed'
    (source / 'benchmark.json').write_text(json.dumps(original))
    archive(source, destination)
    assert json.loads(destination.with_suffix('.json').read_text()) == original
    assert sorted(p.suffix for p in destination.parent.iterdir()) == ['.json', '.md']
    with pytest.raises(FileExistsError):
        archive(source, destination)


def test_software_fingerprint_ignores_machine_paths_and_timestamps():
    from freemocap.tools.machine_benchmarks import software_digest
    a = dict(started_utc='earlier', packages={'numpy': {'version': '2', 'module_path': '/first'}},
             repositories={'freemocap': {'head': 'abc', 'path': '/first', 'tracked_diff_sha256': '123', 'untracked_files': {}}})
    b = copy.deepcopy(a)
    b['started_utc'] = 'later'
    b['packages']['numpy']['module_path'] = '/second'
    b['repositories']['freemocap']['path'] = '/second'
    assert software_digest(a) == software_digest(b)
    b['repositories']['freemocap']['tracked_diff_sha256'] = 'changed'
    assert software_digest(a) != software_digest(b)


def test_comparison_expands_globs_for_windows_shells_and_deduplicates(tmp_path):
    from freemocap.tools.machine_benchmarks import read_records
    path = tmp_path / 'one.json'
    path.write_text('{"example": 1}')
    assert read_records([tmp_path / '*.json', path, tmp_path]) == [{'example': 1}]
    with pytest.raises(ValueError, match='No benchmark'):
        read_records([tmp_path / 'missing-*.json'])


def test_failed_run_keeps_stage_evidence_and_comparison_excludes_it(tmp_path):
    from freemocap.tools.machine_benchmarks import render
    attempt = tmp_path / 'prepared/freemocap_test_data/attempts/one'
    attempt.mkdir(parents=True)
    (attempt / 'performance.json').write_text(json.dumps(dict(status='failed', elapsed_s=2)))
    report = dict(version=1, pipeline_id='one', scope='dataset_worker', outcome='failed',
                  elapsed_s=1.25, frames=0, images=0, counts={},
                  stages={'workflow.blender_preparation': dict(count=1, total_s=1.23456789,
                      mean_ms=1234.56789, first_ms=1234.56789, mean_after_first_ms=None, max_ms=1234.56789)})
    (attempt / 'processing.log').write_text('INFO Processing performance: ' + json.dumps(report))
    case = collect_dataset(tmp_path, 'test_data', 'standard', 'rtmpose')
    assert case['timing_reports'][0]['stages'] == report['stages']
    assert len(case['timing_log_sha256']) == 64
    envelope = dict(schema_version=1, machine=dict(label='mac', cpu='CPU', memory_bytes=24*2**30),
                    conditions='fixture', started_utc='fixture', status='failed', provenance={}, cases=[case])
    text = render(envelope)
    assert 'workflow.blender_preparation' in text
    assert 'Amortized ms/frame' in text
    assert 'not recorded' in text
    assert compare([envelope])['groups'][0]['successful_run_statistics'] == {}


def test_stage_comparison_keeps_per_call_and_per_frame_distinct():
    source = record('mac', dict(kind='dataset', dataset='test_data'), 10)
    source['cases'][0]['timing_reports'] = [dict(scope='posthoc', frames=2, images=6, stages={
        'inference': dict(count=1, total_s=3, mean_ms=3000, mean_after_first_ms=None,
                          first_ms=3000, max_ms=3000)})]
    metrics = compare([source])['groups'][0]['successful_run_statistics']['mac']
    assert metrics['posthoc.inference.mean_ms']['median'] == 3000
    assert metrics['posthoc.inference.amortized_ms_per_frame']['median'] == 1500
    assert metrics['posthoc.inference.amortized_ms_per_image']['median'] == 500
    assert 'posthoc.inference.mean_after_first_ms' not in metrics
