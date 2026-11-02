"""SDK-driven live acceptance. Requires an explicitly assigned camera/GPU slot."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import tomllib
from urllib.parse import urlparse
import socket
import psutil
from skellycam.core.camera.config.camera_config import CameraConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.tools.hardware_validation.server_session import ServerSession
from freemocap.tools.hardware_validation.frame_checks import audit_recording, decode_image_payload, image_metrics
from freemocap.tools.sdk_validation import digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-root', type=Path, required=True)
    parser.add_argument('--camera-configs', type=Path, required=True)
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--electron', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    before = {str(path.resolve()): digest(path) for path in (args.camera_configs, args.calibration)}
    configs = json.loads(args.camera_configs.read_text(encoding='utf-8'))
    sizes = {}
    for identity, value in configs.items():
        camera = CameraConfig.model_validate(value)
        width, height = camera.resolution.width, camera.resolution.height
        if camera.rotation.value in (0, 2):
            width, height = height, width
        sizes[identity] = {'width': width, 'height': height}
    identities = {}
    session = ServerSession(output)
    node = None

    def remember(pid):
        try:
            parent = psutil.Process(pid)
            for process in [parent, *parent.children(recursive=True)]:
                identities[process.pid] = process.create_time()
        except psutil.NoSuchProcess:
            pass

    try:
        with session:
            remember(session.process.pid)
            (output / 'input-hashes.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
            calibrations = output / 'data' / 'calibrations'
            calibrations.mkdir(exist_ok=True)
            shutil.copyfile(args.calibration, calibrations / 'last_successful_camera_calibration.toml')
            board = tomllib.loads(args.calibration.read_text(encoding='utf-8')).get('metadata', {}).get('board')
            pipeline = RealtimePipelineConfig(camera_node_config={} if board is None else {'charuco_board': board})
            pipeline.aggregator_config.skeleton_fitting_enabled = True
            pipeline.skeleton_inference_node_config.execution_provider = 'cuda'
            config = {'url': session.api_client.server_url, 'pid': session.server_pid, 'output': str(output),
                'cameraConfigs': configs, 'imageSizes': sizes,
                'pipelineConfig': pipeline.model_dump(mode='json', exclude_computed_fields=True),
                'recordingDirectory': str(output / 'data' / 'recordings'),
                'uiRoot': str(Path.cwd() / 'freemocap-ui')}
            config_path = output / 'sdk-live-config.json'
            config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
            environment = os.environ.copy()
            environment['FREEMOCAP_TEST_ELECTRON'] = str(args.electron.resolve())
            with (output / 'node-run.log').open('w', encoding='utf-8') as log:
                node = subprocess.Popen(['node', str(args.sdk_root.resolve() / 'tests/live-acceptance.mjs'), str(config_path)],
                    cwd=args.sdk_root, env=environment, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                deadline = time.monotonic() + 330
                while node.poll() is None:
                    remember(node.pid)
                    remember(session.process.pid)
                    if time.monotonic() > deadline:
                        raise TimeoutError('Bounded live acceptance exceeded 330 seconds')
                    time.sleep(0.5)
                assert node.returncode == 0, f'SDK live acceptance failed: {output / "node-run.log"}'
            remember(session.process.pid)
        report = json.loads((output / 'sdk-live-report.json').read_text(encoding='utf-8'))
        recordings = [audit_recording(Path(item['recording_path']), tuple(configs)) for item in report['recordings']]
        assert all(item['matching_camera_frame_indices'] and all(camera['video_matches_capture_timestamps'] for camera in item['cameras'].values()) for item in recordings)
        images = decode_image_payload((output / 'image.bin').read_bytes())
        assert {image.camera_id for image in images} == set(configs)
        (output / 'media-audit.json').write_text(json.dumps({'recordings': recordings,
            'images': {image.camera_id: image_metrics(image.image_pixels) for image in images}}, indent=2), encoding='utf-8')
        print('SDK live capture, production UI, recorded media and image decoding passed', flush=True)
    finally:
        # Terminate only identities created beneath this test, never a port search.
        if node is not None and node.poll() is None:
            remember(node.pid)
            for pid, created in reversed(list(identities.items())):
                try:
                    process = psutil.Process(pid)
                    if process.create_time() == created:
                        process.terminate()
                except psutil.NoSuchProcess:
                    pass
            node.wait(timeout=10)
        if session.owns_output_directory:
            time.sleep(2)
            survivors = []
            for pid, created in identities.items():
                try:
                    if psutil.Process(pid).create_time() == created:
                        survivors.append(pid)
                except psutil.NoSuchProcess:
                    pass
            port_open = False
            if session.api_client is not None:
                url = urlparse(session.api_client.server_url)
                try:
                    with socket.create_connection((url.hostname, url.port), timeout=1):
                        port_open = True
                except OSError:
                    pass
            after = {str(path.resolve()): digest(path) for path in (args.camera_configs, args.calibration)}
            (output / 'delayed-cleanup.json').write_text(json.dumps({'owned_identities': identities,
                'survivors': survivors, 'port_open': port_open, 'inputs_unchanged': before == after}, indent=2), encoding='utf-8')
            assert not survivors and not port_open and before == after


if __name__ == '__main__':
    main()
