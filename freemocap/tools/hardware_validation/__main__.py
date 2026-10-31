"""Run with the repository's existing Python environment; no environment changes."""
import argparse
import json
from pathlib import Path

from freemocap.tools.hardware_validation.server_session import ServerSession
from freemocap.tools.hardware_validation.stream_client import StreamClient


def run_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['server-smoke', 'ui-idle', 'matrix-plan', 'camera-baseline', 'camera-suite', 'pipeline-benchmark'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--camera-ids', nargs='+')
    parser.add_argument('--backend', choices=['python', 'rust', 'both'], default='both')
    parser.add_argument('--suite', choices=['quick', 'extended'], default='quick')
    parser.add_argument('--case', action='append', default=[])
    parser.add_argument('--calibration', type=Path)
    parser.add_argument('--recording-info', type=Path)
    parser.add_argument('--with-ui', action='store_true')
    parser.add_argument('--compare-compression', action='store_true')
    parser.add_argument('--exposure', type=int, help='Override manual exposure in camera-baseline or pipeline-benchmark')
    arguments = parser.parse_args()
    if arguments.command == 'ui-idle':
        import subprocess
        with ServerSession(arguments.output) as session:
            with (session.output_directory / 'ui-console.log').open('w', encoding='utf-8') as output:
                result = subprocess.run(['node', 'tools/hardware-ui.mjs', '--server', session.api_client.server_url,
                    '--output', str(session.output_directory / 'ui'), '--seconds', '5', '--idle-only', 'true'],
                    cwd=Path(__file__).resolve().parents[3] / 'freemocap-ui', stdout=output, stderr=subprocess.STDOUT,
                    timeout=180, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        raise SystemExit(result.returncode)
    if arguments.command == 'pipeline-benchmark':
        if not arguments.calibration or not arguments.recording_info:
            parser.error('pipeline-benchmark requires --calibration and --recording-info')
        from freemocap.tools.hardware_validation.pipeline_run import run_pipeline
        results = []
        for backend in (('python', 'rust') if arguments.backend == 'both' else (arguments.backend,)):
            result = run_pipeline(arguments.output / backend, backend, arguments.calibration,
                                  arguments.recording_info, arguments.with_ui, arguments.compare_compression, arguments.exposure)
            results.append(result)
            print(json.dumps({'backend': backend, 'status': result['status'], 'error': result.get('error')}), flush=True)
        raise SystemExit(0 if all(result['status'] == 'measured' for result in results) else 1)
    if arguments.command == 'camera-suite':
        from freemocap.tools.hardware_validation.suite_runner import run_suite
        results = []
        for backend in (('python', 'rust') if arguments.backend == 'both' else (arguments.backend,)):
            results.append(run_suite(arguments.output / backend, backend, arguments.suite, tuple(arguments.case)))
        raise SystemExit(0 if all(result['passed'] for result in results) else 1)
    if arguments.command == 'camera-baseline':
        from freemocap.tools.hardware_validation.hardware_run import run_baseline
        backends = ('python', 'rust') if arguments.backend == 'both' else (arguments.backend,)
        failures = []
        for backend in backends:
            result = run_baseline(arguments.output / backend, backend,
                                  None if arguments.camera_ids is None else tuple(arguments.camera_ids),
                                  arguments.exposure, arguments.recording_info)
            print(json.dumps({'backend': backend, 'status': result['status'], 'error': result.get('error')}), flush=True)
            if result['status'] != 'passed':
                failures.append(backend)
        if failures:
            raise SystemExit(1)
        return
    if arguments.command == 'matrix-plan':
        from freemocap.tools.hardware_validation.matrix_plan import MatrixPlan
        if not arguments.camera_ids:
            parser.error('matrix-plan requires --camera-ids')
        plan = MatrixPlan(tuple(arguments.camera_ids))
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        if arguments.output.exists():
            parser.error('Refusing to overwrite an existing matrix manifest')
        plan.write_manifest(arguments.output)
        print(json.dumps(plan.counts(), indent=2))
        return
    with ServerSession(arguments.output) as session:
        openapi = session.api_client.request('GET', '/openapi.json')
        with StreamClient(session.api_client.server_url) as stream:
            app_state = stream.wait_for_state()
        (session.output_directory / 'server-smoke.json').write_text(json.dumps({
            'openapi_paths': len(openapi['paths']), 'initial_state': app_state,
        }, indent=2), encoding='utf-8')
    print(f'Server smoke completed: {arguments.output}')


if __name__ == '__main__':
    run_main()
