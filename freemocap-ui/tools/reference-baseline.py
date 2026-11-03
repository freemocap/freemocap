"""Extract measured stage times and independently hash accepted reference files."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--prepared-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
results = {}
for name in ('freemocap_test_data', 'freemocap_sample_data'):
    marker_path = args.prepared_root / name / 'ready.json'
    marker = json.loads(marker_path.read_text())
    result = marker['result']
    recording = Path(marker['recording'])
    if not recording.resolve().is_relative_to((args.prepared_root / name / 'current').resolve()):
        raise ValueError(f'Recording escapes prepared root: {recording}')
    files = [recording / f'{name}_data.parquet', recording / result['calibration_filename']]
    checksums = {}
    for file in files:
        with file.open('rb') as stream:
            checksums[file.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    expected = result['validation']['parquet_sha256']
    if checksums[f'{name}_data.parquet'] != expected:
        raise ValueError(f'Parquet differs from acceptance marker: {name}')
    results[name] = {
        'profile': marker.get('workflow', {}).get('output_profile'),
        'worker': result['performance'],
        'calibration_solver_seconds': result['calibration'].get('time_seconds'),
        'mocap_timing': result['mocap_task']['timing'],
        'operations': [{key: operation.get(key) for key in ('operation_id', 'label', 'status', 'elapsed_seconds', 'completed', 'total', 'unit')}
                       for operation in result['mocap_task']['operations']],
        'sha256': checksums,
        'software': marker['identity']['software'],
    }
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps({name: {'worker_s': data['worker']['elapsed_s'], 'mocap': data['mocap_timing'], 'sha256': data['sha256']} for name, data in results.items()}, indent=2))
