"""Execute the published source examples against an owned CPU-only test server."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from freemocap.tools.hardware_validation.server_session import ServerSession
from freemocap.tools.sdk_validation import digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-root', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.reference.resolve()
    original = digest(source)
    output = args.output.resolve()
    session = ServerSession(output)
    try:
        with session:
            parent = output / 'references'
            folder = parent / source.parent.name
            folder.mkdir(parents=True)
            for item in source.parent.iterdir():
                if item.is_file() and (item == source or item.suffix in ('.json', '.toml')):
                    shutil.copy2(item, folder / item.name)
            commands = [('inspect-server', []), ('stream', ['2']),
                        ('recording', [folder.name, str(parent)]), ('export', [folder.name, str(parent)])]
            results = []
            for name, extra in commands:
                command = ['node', f'examples/{name}.mjs', session.api_client.server_url, *extra]
                run = subprocess.run(command, cwd=args.sdk_root, capture_output=True, text=True, encoding='utf-8',
                    timeout=150, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                (output / f'{name}.log').write_text(run.stdout + run.stderr, encoding='utf-8')
                assert run.returncode == 0, f'{name}: {run.stderr}'
                if name == 'inspect-server':
                    assert json.loads(run.stdout)['health']['pid'] == session.server_pid
                elif name == 'stream':
                    snapshots = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
                    snapshot = next(item for item in snapshots if 'messageKinds' in item)
                    assert {'app_state', 'progress'} <= set(snapshot['messageKinds'])
                elif name == 'recording':
                    channels = json.loads(run.stdout)['runs']['0']
                    assert len(channels) == 36
                    assert next(item for item in channels if item['kind'] == 'LANDMARKS_3D')['frames'] == 222
                elif name == 'export':
                    result = json.loads(run.stdout)
                    assert result['task']['status'] == 'complete' and result['catalog']['artifacts']
                results.append({'example': name, 'exit_code': run.returncode, 'validated': True})
            (output / 'examples-report.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
            print('All four examples executed and validated', flush=True)
    finally:
        assert digest(source) == original, 'Source reference changed'
        if session.owns_output_directory:
            (output / 'source-integrity.json').write_text(json.dumps({'sha256': original, 'unchanged': True}), encoding='utf-8')


if __name__ == '__main__':
    main()
