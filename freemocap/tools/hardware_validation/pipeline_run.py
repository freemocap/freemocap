"""Measure the actual cameras, calibrated pipeline, and optionally the production UI."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import time
import tomllib
import traceback

import numpy as np
from skellycam.core.camera.config.image_rotation_types import RotationTypes

from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.tools.hardware_validation.frame_checks import audit_recording, timing_metrics
from freemocap.tools.hardware_validation.hardware_run import save_json
from freemocap.tools.hardware_validation.server_session import ServerSession
from freemocap.tools.hardware_validation.stream_client import StreamClient


def channel_observations(message: dict) -> list[dict]:
    observations = []
    for collection_name in ('trackers', 'instances'):
        for source in message.get(collection_name, ()):
            for channel in source['channels']:
                values = np.frombuffer(channel['data'], dtype='<f4').reshape(-1, len(channel['columns']))
                observations.append({'collection': collection_name, 'model_id': source['model_id'],
                    'kind': channel['kind'], 'camera_id': channel.get('camera_id'),
                    'shape': list(values.shape), 'finite_values': int(np.isfinite(values).sum()),
                    'value_count': values.size})
    return observations


def run_pipeline(output_directory: Path, backend: str, calibration_path: Path, recording_info_path: Path,
                 with_ui: bool = False, compare_compression: bool = False, exposure: int | None = None) -> dict:
    report = {'backend': backend, 'status': 'failed', 'with_ui': with_ui}
    session = ServerSession(output_directory)
    try:
        with session:
            api = session.api_client
            info = json.loads(recording_info_path.read_text(encoding='utf-8'))
            configs = info['camera_configs']
            for config in configs.values():
                if isinstance(config['rotation'], str):
                    config['rotation'] = RotationTypes[config['rotation']].value
                config.update(use_this_camera=True, framerate=30.0, exposure_mode='MANUAL')
                if exposure is not None:
                    config['exposure'] = exposure
            calibration_directory = output_directory / 'data' / 'calibrations'
            calibration_directory.mkdir(exist_ok=True)
            shutil.copyfile(calibration_path, calibration_directory / 'last_successful_camera_calibration.toml')
            report['calibration_path'] = str(calibration_path.resolve())
            report['camera_configs'] = configs
            save_json(output_directory / 'requested-camera-configs.json', configs)
            api.request('POST', '/skellycam/camera/group/apply', {'camera_configs': configs, 'backend': backend})
            configuration = RealtimePipelineConfig()
            board = tomllib.loads(calibration_path.read_text(encoding='utf-8')).get('metadata', {}).get('board')
            if board is not None:
                configuration.camera_node_config.charuco_board = type(configuration.camera_node_config.charuco_board).model_validate(board)
            configuration.aggregator_config.skeleton_fitting_enabled = True
            configuration.skeleton_inference_node_config.execution_provider = 'cuda'
            report['pipeline_config'] = configuration.model_dump(mode='json', exclude_computed_fields=True)
            api.request('POST', '/freemocap/realtime/apply', {'cameraConfigs': None, 'realtimeCameraIds': None,
                'realtimeConfig': report['pipeline_config']}, timeout_seconds=180.0)
            with StreamClient(api.server_url) as stream:
                stream.request_image_sizes(configs)
                deadline = time.monotonic() + 180.0
                while time.monotonic() < deadline:
                    stream.wait_for_frames(timeout_seconds=30.0)
                    if any(message.get('trackers') for _, message in stream.messages):
                        break
                else:
                    raise TimeoutError('No tracked frames within three minutes')
                # Model/session startup and inference warmup do not belong in steady-state FPS.
                stream.collect_frames(5.0)
                if compare_compression:
                    stream.close()
                    report['compression_phases'] = []
                    for compression in ('deflate', None, None, 'deflate'):
                        with StreamClient(api.server_url, compression=compression) as phase:
                            phase.request_image_sizes(configs)
                            phase.collect_frames(2.0)
                            samples = phase.collect_frames(5.0)
                            report['compression_phases'].append({'compression': compression,
                                'negotiated_extensions': phase.socket.response.headers.get('Sec-WebSocket-Extensions'),
                                'delivery': timing_metrics(np.asarray([received for received, _ in samples]),
                                    np.asarray([message['frame_number'] for _, message in samples]))})
                elif with_ui:
                    observed_configs = {identity: config for group in stream.wait_for_state()['camera_groups'].values()
                                        for identity, config in group['configs'].items()}
                    save_json(output_directory / 'observed-camera-configs.json', observed_configs)
                    # Close the diagnostic subscriber: a second JPEG consumer changes the workload.
                    stream.close()
                    ui_root = Path(__file__).resolve().parents[3] / 'freemocap-ui'
                    with (output_directory / 'ui-console.log').open('w', encoding='utf-8') as output:
                        result = subprocess.run(['node', 'tools/hardware-ui.mjs', '--server', api.server_url,
                            '--output', str((output_directory / 'ui').resolve()), '--seconds', '20',
                            '--expected-configs', str((output_directory / 'observed-camera-configs.json').resolve())],
                            cwd=ui_root, stdout=output, stderr=subprocess.STDOUT, timeout=240,
                            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    if result.returncode != 0:
                        raise RuntimeError(f'Production UI measurement failed; inspect {output_directory / "ui-console.log"}')
                else:
                    api.request('POST', '/skellycam/camera/group/all/record/start', {
                        'recording_name': 'tracked-capture', 'recording_directory': str((output_directory / 'data' / 'recordings').resolve()),
                        'mic_device_index': -1})
                    samples = stream.collect_frames(5.0)
                    recordings = api.request('GET', '/skellycam/camera/group/all/record/stop')
                    report['recording_response'] = recordings
                    timestamps = np.asarray([received for received, _ in samples])
                    frame_numbers = np.asarray([message['frame_number'] for _, message in samples])
                    report['processed_delivery'] = timing_metrics(timestamps, frame_numbers)
                    report['channels'] = channel_observations(samples[-1][1])
                    np.savez(output_directory / 'processed-timing.npz', arrival_seconds=timestamps,
                        frame_numbers=frame_numbers, source_timestamp_ns=np.asarray([message['timestamp'] for _, message in samples]))
            # Release GPU/capture workers before decoding recordings for verification.
            api.request('DELETE', '/freemocap/mocap/realtime/pipelines')
            api.request('DELETE', '/skellycam/camera/group/close/all')
            report['recordings'] = [audit_recording(Path(recording['recording_path']), tuple(configs))
                for recording in report.get('recording_response', ())]
            report['status'] = 'measured'
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        report['traceback'] = traceback.format_exc()
    finally:
        if session.owns_output_directory:
            save_json(output_directory / 'pipeline-report.json', report)
    return report
