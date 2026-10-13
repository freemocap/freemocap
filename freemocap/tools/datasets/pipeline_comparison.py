"""Run both production entry points on the same videos and calibration."""
import argparse
import json
from pathlib import Path
import shutil

from . import workflow
from .preparation import file_digest
from .storage import write_json


def compare_pipelines(*, recordings_root: Path, prepared_root: Path, output: Path,
                      datasets: tuple[str, ...] = ('test_data', 'sample_data')) -> dict:
    output = output.resolve()
    if output.exists():
        raise ValueError('Comparison output must be a new directory')
    for root in (recordings_root.resolve(), prepared_root.resolve()):
        if output.is_relative_to(root) or root.is_relative_to(output):
            raise ValueError('Comparison output must be separate from source and prepared recordings')
    # Resolve accepted calibration once, before either implementation can change it.
    calibrations = {}
    for name in datasets:
        ready = workflow.checked_ready(prepared_root / workflow.DATASETS[name].name)
        if ready is None:
            raise ValueError(f'Prepare {name} first to establish shared calibration')
        calibrations[name] = Path(ready['recording']) / ready['result']['calibration_filename']
    output.mkdir(parents=True)
    report = dict(status='running', scope='independent full mocap runs, same source videos and calibration',
                  output_profile='standard (Parquet and validated Blender; no CSV/NPY/NPZ)', datasets={})
    for name in datasets:
        calibration = output / f'{name}-calibration.toml'
        shutil.copy2(calibrations[name], calibration)
        calibration_hash = file_digest(calibration)
        entry = report['datasets'][name] = dict(calibration_sha256=calibration_hash, runs={}, parity=None)
        for implementation in ('current', 'graph'):
            try:
                recording = workflow.process(name, recordings_root=recordings_root,
                    prepared_root=output / implementation, calibration=str(calibration),
                    implementation=implementation)
                ready = json.loads((output / implementation / workflow.DATASETS[name].name / 'ready.json').read_text())
                result = ready['result']
                expected = 'typed_dataflow' if implementation == 'graph' else 'current'
                if result['mocap_config']['pipeline_implementation'] != expected:
                    raise ValueError('Executed pipeline does not match selected pipeline')
                if file_digest(calibration) != calibration_hash:
                    raise ValueError('Shared calibration input was modified')
                entry['runs'][implementation] = dict(status='complete', recording=str(recording),
                    mocap_seconds=result['mocap_task']['timing']['elapsed_seconds'],
                    motion_frames=result['mocap_task']['timing']['motion_frame_count'],
                    worker_seconds=result['performance']['elapsed_s'],
                    config=result['mocap_config'], source=ready['identity']['source'], log=ready['log'])
            except Exception as error:
                entry['runs'][implementation] = dict(status='failed', error=f'{type(error).__name__}: {error}')
            write_json(output / 'comparison.json', report)
        if all(r['status'] == 'complete' for r in entry['runs'].values()):
            from .full_recording_comparison import compare_saved_channels
            from freemocap.core.pipeline.posthoc.saved_stage_processing import recording_structure
            old, new = (entry['runs'][key] for key in ('current', 'graph'))
            try:
                if old['source'] != new['source']:
                    raise ValueError('Input recording identity differs')
                configs = [dict(run['config']) for run in (old, new)]
                for config in configs:
                    for key in ('pipeline_implementation', 'calibration_toml_path'):
                        config.pop(key)
                if configs[0] != configs[1]:
                    raise ValueError('Scientific/export settings differ between runs')
                channels = compare_saved_channels(recording_structure(old['recording']), recording_structure(new['recording']))
                entry['parity'] = dict(status='passed', channels=channels)
            except Exception as error:
                entry['parity'] = dict(status='failed', error=f'{type(error).__name__}: {error}')
            entry['mocap_speedup'] = old['mocap_seconds'] / new['mocap_seconds']
        write_json(output / 'comparison.json', report)
    report['status'] = 'passed' if all(e['parity'] and e['parity']['status'] == 'passed'
                                      for e in report['datasets'].values()) else 'failed'
    write_json(output / 'comparison.json', report)
    lines = ['FULL PIPELINE COMPARISON', report['scope'], report['output_profile'], f"Status: {report['status']}"]
    for name, entry in report['datasets'].items():
        lines.append(f'\n{name}')
        for implementation, run in entry['runs'].items():
            if run['status'] == 'complete':
                lines.append(f"  {implementation}: mocap {run['mocap_seconds']:.3f} s; "
                             f"{1000 * run['mocap_seconds'] / run['motion_frames']:.2f} ms/motion frame; "
                             f"worker including validation {run['worker_seconds']:.3f} s")
            else:
                lines.append(f"  {implementation}: FAILED {run['error']}")
        parity = entry['parity']
        if parity and parity['status'] == 'passed':
            channels = parity['channels']
            maximum = max((c['maximum_absolute_error'] for c in channels), default=0)
            lines.append(f'  Parity: passed; {len(channels)} channels; largest absolute difference {maximum:.9g}')
        else:
            lines.append(f"  Parity: {parity}")
    (output / 'comparison.txt').write_text('\n'.join(lines), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recordings-root', type=Path, default=Path.home() / 'freemocap_data/recordings')
    parser.add_argument('--prepared-root', type=Path, default=Path.home() / 'freemocap_data/testing/prepared')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = compare_pipelines(**vars(args))
    print((args.output / 'comparison.txt').read_text(encoding='utf-8'))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
