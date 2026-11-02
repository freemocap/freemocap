"""Replay saved numerical channels through canonical encoding and real sockets.

This is transport replay, not an inference rerun or a throughput benchmark.
Every packet includes its model and convention, including late-joining clients.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
from threading import Thread
import time
from urllib.parse import urlparse, parse_qs

import numpy as np
from websockets.sync.server import serve
from websockets.exceptions import ConnectionClosed
from freemocap.core.recording.playback_queries import playback_manifest
from freemocap.core.streaming.message_model import ChannelBlock, ChannelKind, FrameMessage, MessageEnvelope, ModelInstance, encode_message


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acceptance-output', type=Path, required=True)
    parser.add_argument('--sdk-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads((args.acceptance_output / 'sdk-config.json').read_text(encoding='utf-8'))
    prepared = []
    for reference in config['recordings']:
        expected = json.loads(Path(reference['expected']).read_text(encoding='utf-8'))
        source = Path(reference['parent']) / reference['id'] / f"{reference['id']}_data.parquet"
        manifest = playback_manifest(source)
        run = next(run for run in manifest.runs if run.run_id == expected['run_id'])
        model = next(model for model in run.models if model.model_id == run.model_sources[expected['channel']['source']])
        assert [landmark.name for landmark in model.landmarks] == expected['channel']['names']
        values = np.array(expected['values'], dtype='<f4').reshape(len(expected['frames']), -1)
        packets = [encode_message(FrameMessage(
            envelope=MessageEnvelope(timestamp=float(expected['times'][slot]), sequence=frame), frame_number=frame,
            models=(model,), instances=(ModelInstance(instance_id=0, model_id=model.model_id,
                channels=(ChannelBlock(kind=ChannelKind.LANDMARKS_3D,
                    columns=tuple(expected['channel']['components']), data=values[slot].tobytes()),)),)))
            for slot, frame in enumerate(expected['frames'])]
        prepared.append(packets)
    feedback = []
    failures = []

    def handle(connection):
        try:
            request = urlparse(connection.request.path)
            index = int(request.path.split('/')[1])
            start = int(parse_qs(request.query).get('start', ['0'])[0])
            connection.send('ping')
            assert connection.recv(timeout=5) == 'pong'
            for packet in prepared[index][start:]:
                connection.send(packet)
                time.sleep(0.003)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                value = connection.recv(timeout=5)
                if value == 'ping':
                    connection.send('pong')
                else:
                    message = json.loads(value)
                    if 'frameNumber' in message:
                        feedback.append({'recording': index, 'start': start, **message})
                        break
            assert feedback and feedback[-1]['recording'] == index and feedback[-1]['start'] == start
            connection.recv(timeout=5)
        except ConnectionClosed:
            pass
        except Exception as error:
            failures.append(repr(error))

    with serve(handle, '127.0.0.1', 0, compression=None) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config.update(url=f'http://127.0.0.1:{server.socket.getsockname()[1]}', report=str(output / 'sdk-replay-report.json'))
        path = output / 'config.json'
        path.write_text(json.dumps(config, indent=2), encoding='utf-8')
        try:
            result = subprocess.run(['node', str(args.sdk_root.resolve() / 'tests/replay-acceptance.mjs'), str(path)],
                capture_output=True, text=True, encoding='utf-8', timeout=180,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            (output / 'node-run.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            print(result.stdout, flush=True)
            assert result.returncode == 0, result.stderr
            assert not failures, failures
            assert len(feedback) == 2 * len(prepared), feedback
        finally:
            server.shutdown()
            thread.join(timeout=5)
            (output / 'cleanup.json').write_text(json.dumps({'server_thread_alive': thread.is_alive(),
                'handler_errors': failures, 'display_feedback': feedback}, indent=2), encoding='utf-8')
            assert not thread.is_alive()


if __name__ == '__main__':
    main()
