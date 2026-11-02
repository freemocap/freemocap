"""Run the standalone SDK against an owned server and private reference copies.

No cameras or inference sessions are opened. Scientific expected values come
from PyArrow rows, independently of the JavaScript recording reader.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import pyarrow.parquet as pq

from freemocap.core.recording.playback_queries import playback_manifest
from freemocap.tools.hardware_validation.server_session import ServerSession


def digest(path: Path) -> str:
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def reference_expectation(path: Path, expected_frames: int) -> dict:
    manifest = playback_manifest(path)
    run = next(run for run in manifest.runs if run.run_id == manifest.selected_run_id)
    channel = next(channel for channel in run.channels if channel.kind == 'LANDMARKS_3D')
    filters = [('run_id', '=', run.run_id), ('sensor_group', '=', channel.sensor_group),
               ('source', '=', channel.source), ('channel', '=', str(channel.kind))]
    if channel.reference_frame is not None:
        filters.append(('reference_frame', '=', channel.reference_frame))
    columns = pq.read_table(path, filters=filters,
        columns=['reference_frame', 'frame_number', 'timestamp_s', 'name', 'component', 'value']).to_pydict()
    indices = [index for index, reference in enumerate(columns['reference_frame']) if reference == channel.reference_frame]
    frames = sorted({columns['frame_number'][index] for index in indices})
    assert len(frames) == expected_frames, (path, len(frames), expected_frames)
    frame_slots = {frame: slot for slot, frame in enumerate(frames)}
    names = {name: slot for slot, name in enumerate(channel.names)}
    components = {component: slot for slot, component in enumerate(channel.components)}
    stride = len(names) * len(components)
    values = [None] * (len(frames) * stride)
    times = [None] * len(frames)
    seen = set()
    for index in indices:
        slot = frame_slots[columns['frame_number'][index]]
        offset = slot * stride + names[columns['name'][index]] * len(components) + components[columns['component'][index]]
        assert offset not in seen, 'Duplicate reference value'
        seen.add(offset)
        time = columns['timestamp_s'][index]
        assert times[slot] in (None, time), 'Inconsistent reference timestamp'
        times[slot] = time
        value = columns['value'][index]
        values[offset] = value if value is not None and math.isfinite(value) else None
    return {'run_id': run.run_id, 'channel': channel.model_dump(mode='json'),
            'frames': frames, 'times': times, 'values': values}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-root', type=Path, required=True)
    parser.add_argument('--reference', nargs=2, action='append', required=True, metavar=('PARQUET', 'FRAMES'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sdk = args.sdk_root.resolve()
    sources = [(Path(path).resolve(), int(frames)) for path, frames in args.reference]
    before = {str(path): digest(path) for path, _ in sources}
    output = args.output.resolve()
    session = ServerSession(output)
    try:
        with session:
            root = output / 'references'
            root.mkdir()
            recordings = []
            for source, frames in sources:
                folder = root / source.parent.name
                folder.mkdir()
                for item in source.parent.iterdir():
                    if item.is_file() and (item == source or item.suffix in ('.json', '.toml')):
                        shutil.copy2(item, folder / item.name)
                expected = output / f'{source.parent.name}-expected.json'
                expected.write_text(json.dumps(reference_expectation(source, frames), allow_nan=False), encoding='utf-8')
                recordings.append({'id': folder.name, 'parent': str(root), 'expected': str(expected),
                                   'sha256': before[str(source)]})
            config = {'url': session.api_client.server_url, 'pid': session.server_pid, 'recordings': recordings,
                      'report': str(output / 'sdk-report.json')}
            config_path = output / 'sdk-config.json'
            config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
            result = subprocess.run(['node', str(sdk / 'tests/server-acceptance.mjs'), str(config_path)],
                cwd=sdk, capture_output=True, text=True, encoding='utf-8', timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            (output / 'node-run.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            print(result.stdout, flush=True)
            if result.returncode:
                raise RuntimeError(f'SDK acceptance failed: {result.stderr}')
        # The server is gone: an HTTP transport failure must stay observable.
        offline = subprocess.run(['node', '--input-type=module', '-e',
            "import {createHttpClient} from './dist/http.js'; import assert from 'node:assert/strict'; "
            "const c=createHttpClient({baseUrl:process.argv[1]}); await assert.rejects("
            "()=>c.operations.healthcheck_endpoint_health_get({signal:AbortSignal.timeout(2000)}),"
            "error=>error instanceof TypeError && error.cause?.code==='ECONNREFUSED');", config['url']],
            cwd=sdk, capture_output=True, text=True, encoding='utf-8', timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        assert offline.returncode == 0, offline.stderr
        (output / 'offline-failure.json').write_text(json.dumps({'network_error': 'ECONNREFUSED', 'sdk_rejected': True}), encoding='utf-8')
    finally:
        after = {str(path): digest(path) for path, _ in sources}
        if session.owns_output_directory:
            (output / 'source-integrity.json').write_text(json.dumps({'before': before, 'after': after, 'unchanged': before == after}, indent=2), encoding='utf-8')
        assert before == after, 'Reference source changed'


if __name__ == '__main__':
    main()
