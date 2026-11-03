"""Archive and compare measurements from the existing dataset and camera runners.

This module does not implement processing, camera control, or acceptance checks.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import glob
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import psutil

from freemocap.tools.hardware_validation.provenance import capture_provenance

SCHEMA_VERSION = 1


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def machine_info(label: str) -> dict:
    def query(command):
        try:
            return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
        except (OSError, subprocess.SubprocessError):
            return None
    cpu = platform.processor()
    gpu = None
    if sys.platform == 'darwin':
        cpu = query(['sysctl', '-n', 'machdep.cpu.brand_string']) or cpu
        raw = query(['system_profiler', 'SPDisplaysDataType', '-json'])
        if raw:
            gpu = [{k: v for k, v in item.items() if k in ('sppci_model', 'sppci_cores', 'spdisplays_vram')}
                   for item in json.loads(raw).get('SPDisplaysDataType', [])]
    elif os.name == 'nt':
        cpu = query(['powershell', '-NoProfile', '-Command', '(Get-CimInstance Win32_Processor).Name']) or cpu
        gpu = query(['powershell', '-NoProfile', '-Command', '(Get-CimInstance Win32_VideoController).Name'])
    else:
        gpu = query(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'])
    memory = psutil.virtual_memory()
    try:
        import onnxruntime
        providers = onnxruntime.get_available_providers()
    except ImportError:
        providers = None
    return dict(label=label, os=platform.platform(), architecture=platform.machine(), cpu=cpu,
                physical_cores=psutil.cpu_count(logical=False), logical_cores=psutil.cpu_count(),
                memory_bytes=memory.total, gpu=gpu, available_onnx_providers=providers,
                thread_environment={key: os.environ.get(key) for key in
                    ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMBA_NUM_THREADS')})


def load_snapshot():
    memory = psutil.virtual_memory()
    return dict(available_memory_bytes=memory.available, system_cpu_percent=psutil.cpu_percent(interval=0.2),
                load_average=list(os.getloadavg()) if hasattr(os, 'getloadavg') else None)


def portable(value):
    """Keep paths useful locally; replace user-specific roots in published records."""
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [portable(v) for v in value]
    if isinstance(value, str):
        return value.replace(str(Path.home()), '<HOME>').replace(str(Path.home()).replace('\\', '/'), '<HOME>')
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def timing_rows(value, prefix=''):
    """Keep named existing numeric measurements, without inferring missing rates."""
    rows = {}
    if isinstance(value, dict):
        for key, item in value.items():
            name = f'{prefix}.{key}' if prefix else key
            if key in ('measured_fps', 'p99_interval_ms', 'missing_frame_numbers', 'duplicate_source_frames'):
                rows[name] = item
            elif isinstance(item, (dict, list)):
                rows.update(timing_rows(item, name))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.update(timing_rows(item, f'{prefix}[{index}]'))
    return rows


def collect_dataset(output: Path, dataset: str, profile: str, preset: str) -> dict:
    from freemocap.tools.datasets.workflow import DATASETS
    root = output / 'prepared' / DATASETS[dataset].name
    attempts = list((root / 'attempts').glob('*'))
    attempt = attempts[0] if len(attempts) == 1 else None
    ready = read_json(root / 'ready.json') if (root / 'ready.json').exists() else None
    result = ready['result'] if ready else {}
    performance = read_json(attempt / 'performance.json') if attempt and (attempt / 'performance.json').exists() else None
    workload = dict(kind='dataset', dataset=dataset, output_profile=profile, tracker_preset=preset,
                    calibration='fresh', implementation='graph', filtering=dataset == 'sample_data')
    if ready:
        workload['videos'] = [{k: video[k] for k in ('sha256', 'width', 'height', 'decoded_frames', 'nominal_fps')}
                              for video in ready['identity']['source']['videos']]
    metrics = {}
    if performance:
        metrics['worker_elapsed_s'] = performance['elapsed_s']
        if ready and performance['status'] == 'complete':
            frames = workload['videos'][0]['decoded_frames']
            metrics['synchronized_frames_per_worker_second'] = frames / performance['elapsed_s']
            metrics['camera_images_per_worker_second'] = frames * len(workload['videos']) / performance['elapsed_s']
    log_path = attempt / 'processing.log' if attempt else None
    log_lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines() if log_path and log_path.exists() else []
    summaries = [line for line in log_lines if line.startswith(('Posthoc performance [', 'Completed detection:', 'Detection throughput:'))
                 or 'applied_providers=' in line or 'active providers:' in line]
    return dict(workload=workload, status='passed' if ready else 'failed', metrics=metrics, processing_summaries=summaries,
                worker=performance, executed_settings=result.get('mocap_config'),
                validation=result.get('validation'), calibration=result.get('calibration'))


def collect_camera(output: Path, backend: str) -> list[dict]:
    report_path = output / backend / 'suite-report.json'
    if not report_path.exists():
        return [dict(workload=dict(kind='camera', backend=backend), status='failed', metrics={}, error='Suite report missing')]
    report = read_json(report_path)
    inventory_path = output / backend / 'camera-inventory.json'
    inventory = read_json(inventory_path) if inventory_path.exists() else []
    records = []
    for case in report['cases']:
        definition = case['case']
        kind = definition['control_name'] or ('record' if definition['case_name'].startswith('record-') else definition['case_name'])
        workload = dict(kind='camera', backend=backend, case=kind, camera_count=len(definition['camera_ids']),
                        requested_camera_count=len(definition['requested_ids']), initial_resolution=[1280, 720],
                        requested_fps=30, capture_fourcc='MJPG', writer_fourcc='X264')
        # Physical device identity is evidence, deliberately not a compatibility key.
        metrics = timing_rows(case)
        for index, identity in enumerate(definition['camera_ids']):
            metrics = {key.replace(f'.{identity}.', f'.camera[{index}].'): value for key, value in metrics.items()}
        records.append(dict(workload=workload, status=case['status'], metrics=metrics,
                            elapsed_seconds=case['elapsed_seconds'], camera_inventory=inventory,
                            evidence={key: value for key, value in case.items()
                                      if key not in ('observed_app_state', 'traceback')},
                            server_errors=report['server_errors']))
    if not records:
        records.append(dict(workload=dict(kind='camera', backend=backend), status='failed', metrics={},
                            camera_inventory=inventory, error=report['server_errors']))
    return records


def render(record):
    lines = [f"# Machine benchmark: {record['machine']['label']}", '',
             f"Run: {record['started_utc']} | {record['status']}",
             f"CPU: {record['machine']['cpu']} | RAM: {record['machine']['memory_bytes'] / 2**30:g} GiB", '',
             record['conditions'], '', '| Workload | Status | Measurement | Value |', '|---|---|---|---|']
    for case in record['cases']:
        label = case['workload'].get('dataset') or f"{case['workload'].get('backend')} / {case['workload'].get('case', 'suite')}"
        for metric, value in (case['metrics'] or {'measurements': 'unavailable'}).items():
            display = f'{value:.6g}' if isinstance(value, float) else str(value)
            lines.append(f"| {label} | {case['status']} | {metric} | {display} |")
    errors = [f"- {case['workload'].get('backend', case['workload'].get('dataset', 'run'))} / "
              f"{case['workload'].get('case', '')}: {case.get('error') or case.get('evidence', {}).get('error')}"
              for case in record['cases'] if case.get('error') or case.get('evidence', {}).get('error')]
    if errors:
        lines += ['', 'Recorded failures:', '', *errors]
    lines += ['', 'Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.',
              'Camera measurements come from the existing suite; differing devices are retained as context.',
              'Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.', '']
    return '\n'.join(lines)


def software_digest(provenance):
    # Timestamps and checkout paths are not software differences.
    packages = {name: value['version'] for name, value in provenance.get('packages', {}).items()}
    repositories = {name: {key: value.get(key) for key in ('head', 'tracked_diff_sha256', 'untracked_files')}
                    for name, value in provenance.get('repositories', {}).items()}
    return digest(dict(packages=packages, repositories=repositories))


def compare(records: list[dict]) -> dict:
    groups = {}
    for record in records:
        if record.get('schema_version') != SCHEMA_VERSION:
            raise ValueError('Unsupported benchmark schema')
        for case in record['cases']:
            key = digest(case['workload'])
            group = groups.setdefault(key, dict(workload=case['workload'], measurements=[]))
            metrics = case['metrics']
            for index, identity in enumerate(case.get('evidence', {}).get('case', {}).get('camera_ids', [])):
                metrics = {name.replace(f'.{identity}.', f'.camera[{index}].'): value for name, value in metrics.items()}
            group['measurements'].append(dict(machine=record['machine']['label'], status=case['status'],
                metrics=metrics, software_digest=software_digest(record['provenance']),
                conditions=record['conditions'], camera_inventory=case.get('camera_inventory'),
                selected_camera_ids=case.get('evidence', {}).get('case', {}).get('camera_ids'),
                server_errors=case.get('server_errors', [])))
    # Group only matching workloads; no hardware-independent performance thresholds.
    for group in groups.values():
        machines = {}
        for measurement in group['measurements']:
            if measurement['status'] != 'passed' or measurement.get('server_errors'):
                continue
            for metric, value in measurement['metrics'].items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    machines.setdefault(measurement['machine'], {}).setdefault(metric, []).append(value)
        group['successful_run_statistics'] = {machine: {metric: dict(n=len(values), median=statistics.median(values),
                minimum=min(values), maximum=max(values)) for metric, values in metrics.items()}
                for machine, metrics in machines.items()}
        baseline = next(iter(group['successful_run_statistics'].values()), {})
        for metrics in group['successful_run_statistics'].values():
            for metric, summary in metrics.items():
                reference = baseline.get(metric, {}).get('median')
                summary['ratio_to_first_successful_machine'] = summary['median'] / reference if reference else None
    return dict(schema_version=SCHEMA_VERSION, groups=list(groups.values()),
                interpretation='Compare successful cases with matching workloads. Camera models may differ. '
                'Software, providers, background load and cache state remain confounders; no automatic regression verdict.')


def run(args):
    output = args.output.resolve()
    # A caller may choose an external temporary folder; in a checkout require an ignored path.
    owner = next((p for p in (output, *output.parents) if (p / '.git').exists()), None)
    if owner is not None:
        ignored = subprocess.run(['git', '-C', str(owner), 'check-ignore', '-q', str(output)])
        if ignored.returncode != 0:
            raise ValueError('Benchmark output inside a repository must be ignored; use .test-artifacts/')
    output.mkdir(parents=True, exist_ok=False)
    record = dict(schema_version=SCHEMA_VERSION, started_utc=datetime.now(timezone.utc).isoformat(),
                  machine=machine_info(args.machine), conditions=args.conditions,
                  provenance=portable(capture_provenance()), load_before=load_snapshot(), cases=[], status='running')
    write_json(output / 'benchmark.json', record)
    if args.command == 'dataset':
        command = [sys.executable, '-B', '-m', 'freemocap.tools.datasets', 'process', args.dataset,
                   '--recordings-root', str(args.recordings_root.resolve()), '--prepared-root', str(output / 'prepared'),
                   '--output-profile', args.output_profile, '--tracker-preset', args.tracker_preset,
                   '--timeout', str(args.timeout)]
        if args.blender_path:
            command += ['--blender-path', args.blender_path]
    else:
        command = [sys.executable, '-B', '-m', 'freemocap.tools.hardware_validation', 'camera-suite',
                   '--output', str(output / 'suite'), '--backend', args.backend, '--suite', args.suite]
    record['command'] = portable(command)
    started = time.perf_counter()
    try:
        with (output / 'runner.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        record['returncode'] = result.returncode
        if args.command == 'dataset':
            record['cases'] = [collect_dataset(output, args.dataset, args.output_profile, args.tracker_preset)]
        else:
            for backend in (('python', 'rust') if args.backend == 'both' else (args.backend,)):
                record['cases'] += collect_camera(output / 'suite', backend)
        record['status'] = 'passed' if result.returncode == 0 and record['cases'] and all(c['status'] == 'passed' for c in record['cases']) else 'failed'
    except BaseException as error:
        record.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=str(error))
        raise
    finally:
        record['elapsed_s'] = time.perf_counter() - started
        record['load_after'] = load_snapshot()
        record = portable(record)
        write_json(output / 'benchmark.json', record)
        (output / 'benchmark.md').write_text(render(record), encoding='utf-8')
    print(render(record))
    return 0 if record['status'] == 'passed' else 1


def archive(source: Path, destination: Path) -> None:
    """Publish a reviewed portable record, never bulk camera/dataset artifacts."""
    record = read_json(source / 'benchmark.json')
    if record.get('schema_version') != SCHEMA_VERSION or record.get('status') not in ('passed', 'failed', 'interrupted'):
        raise ValueError('Only completed benchmark reports can be archived')
    targets = [destination.with_suffix('.json'), destination.with_suffix('.md')]
    if any(path.exists() for path in targets):
        raise FileExistsError('Archive destination already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    record = portable(record)
    with targets[0].open('x', encoding='utf-8') as output:
        output.write(json.dumps(record, indent=2, allow_nan=False) + '\n')
    with targets[1].open('x', encoding='utf-8') as output:
        output.write(render(record))


def read_records(patterns):
    paths = []
    for pattern in patterns:
        candidate = Path(pattern)
        matches = sorted(candidate.glob('*.json')) if candidate.is_dir() else [Path(p) for p in sorted(glob.glob(str(pattern))) ]
        if not matches:
            raise ValueError(f'No benchmark JSON files match: {pattern}')
        paths.extend(path.resolve() for path in matches)
    return [read_json(path) for path in dict.fromkeys(paths)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('dataset', 'camera'):
        sub = commands.add_parser(name)
        sub.add_argument('--output', required=True, type=Path, help='New ignored artifact directory')
        sub.add_argument('--machine', required=True, help='Stable public machine label, not hostname')
        sub.add_argument('--conditions', required=True, help='Background load, power mode and cache/warmup conditions')
        if name == 'dataset':
            sub.add_argument('dataset', choices=('test_data', 'sample_data'))
            sub.add_argument('--recordings-root', type=Path, default=Path.home() / 'freemocap_data/recordings')
            sub.add_argument('--output-profile', choices=('standard', 'numerical'), default='standard')
            sub.add_argument('--tracker-preset', choices=('rtmpose', 'mediapipe', 'rtmw_mediapipe_hands'), default='rtmpose')
            sub.add_argument('--blender-path')
            sub.add_argument('--timeout', type=float, default=1800)
        else:
            sub.add_argument('--backend', choices=('python', 'rust', 'both'), default='both')
            sub.add_argument('--suite', choices=('quick', 'extended'), default='extended')
    sub = commands.add_parser('compare')
    sub.add_argument('records', nargs='+', type=Path)
    sub = commands.add_parser('archive', help='Copy reviewed portable JSON/Markdown into the repository')
    sub.add_argument('source', type=Path, help='Existing benchmark artifact directory')
    sub.add_argument('destination', type=Path, help='New filename stem, usually benchmarks/results/date-machine-case-01')
    args = parser.parse_args()
    if args.command == 'archive':
        archive(args.source, args.destination)
        return 0
    if args.command == 'compare':
        print(json.dumps(compare(read_records(args.records)), indent=2))
        return 0
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
