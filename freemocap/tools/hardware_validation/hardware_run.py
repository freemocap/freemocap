"""Run actual production camera routes and keep failures and original evidence."""
from __future__ import annotations

import json
from pathlib import Path
import time
import traceback

import cv2
import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.image_rotation_types import RotationTypes

from freemocap.tools.hardware_validation.frame_checks import audit_recording, decode_image_payload, image_metrics, timing_metrics
from freemocap.tools.hardware_validation.server_session import ServerSession
from freemocap.tools.hardware_validation.stream_client import StreamClient


def save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def make_camera_configs(camera_devices: list[dict], selected_ids: tuple[str, ...], width: int = 1280, height: int = 720) -> dict:
    return {device['camera_id']: CameraConfig(camera_id=device['camera_id'], camera_index=device['index'],
                camera_name=device['name'], resolution={'width': width, 'height': height},
                exposure_mode='MANUAL', exposure=-6, framerate=30.0, rotation=-1,
                capture_fourcc='MJPG', writer_fourcc='X264').model_dump(mode='json')
            for device in camera_devices if device['camera_id'] in selected_ids}


def inspect_stream(samples: list, expected_configs: dict, output_directory: Path, capture_backend: str) -> dict:
    camera_results = {}
    arrivals = []
    source_times = []
    source_numbers = []
    for received, message in samples:
        if message.get('image') is None:
            raise ValueError('Camera frame has no image payload')
        images = decode_image_payload(message['image'])
        if {image.camera_id for image in images} != set(expected_configs):
            raise ValueError('Stream camera identities differ from requested cameras')
        arrivals.append(received)
        source_times.append(message['timestamp'])
        source_numbers.append(images[0].frame_number)
        for image in images:
            expected = expected_configs[image.camera_id]
            if image.camera_index != expected['camera_index']:
                raise ValueError(f'Incorrect device index for {image.camera_id}')
            width, height = expected['resolution']['width'], expected['resolution']['height']
            if CameraConfig.model_validate(expected).rotation.value in (0, 2):
                width, height = height, width
            # Python's production transport caps live previews at half resolution.
            # Rust currently sends full resolution; record this difference explicitly.
            if capture_backend == 'python':
                width, height = width // 2, height // 2
            if image.image_pixels.shape != (height, width, 3):
                raise ValueError(f'Unexpected image shape for {image.camera_id}: {image.image_pixels.shape}')
            if image.camera_id not in camera_results:
                camera_results[image.camera_id] = {'brightness_samples': [], 'first_frame': image_metrics(image.image_pixels)}
            camera = camera_results[image.camera_id]
            camera['brightness_samples'].append(float(cv2.mean(cv2.cvtColor(image.image_pixels, cv2.COLOR_BGR2GRAY))[0]))
            if len(camera['brightness_samples']) == 1:
                cv2.imwrite(str(output_directory / f'camera-{image.camera_id}.jpg'), image.image_pixels)
    np.savez(output_directory / 'frame-observations.npz', received_seconds=np.asarray(arrivals),
             source_timestamp_ns=np.asarray(source_times), source_frame_numbers=np.asarray(source_numbers),
             message_sequences=np.asarray([message['sequence'] for _, message in samples]))
    numbers = np.asarray(source_numbers)
    distinct = np.r_[True, np.diff(numbers) != 0]
    duplicate_count = int(np.count_nonzero(np.diff(numbers) == 0))
    return {'delivery': timing_metrics(np.asarray(arrivals), np.arange(len(arrivals))),
            'source_frames_received': timing_metrics(np.asarray(source_times)[distinct] / 1e9, numbers[distinct]),
            'duplicate_source_frames': duplicate_count, 'continuity_passed': duplicate_count == 0,
            'cameras': camera_results}


def run_baseline(output_directory: Path, capture_backend: str, selected_ids: tuple[str, ...] | None = None,
                 exposure: int | None = None, recording_info_path: Path | None = None) -> dict:
    report = {'capture_backend': capture_backend, 'status': 'failed'}
    session = ServerSession(output_directory)
    try:
        with session:
            api = session.api_client
            devices = api.request('POST', '/skellycam/camera/detect')['cameras']
            save_json(output_directory / 'camera-inventory.json', devices)
            selected = tuple(device['camera_id'] for device in devices) if selected_ids is None else selected_ids
            if not selected or not set(selected) <= {device['camera_id'] for device in devices}:
                raise ValueError(f'Requested cameras unavailable: {selected}')
            configs = make_camera_configs(devices, selected)
            if recording_info_path is not None:
                saved = json.loads(recording_info_path.read_text(encoding='utf-8'))['camera_configs']
                configs = {identity: saved[identity] for identity in selected}
                for config in configs.values():
                    if isinstance(config['rotation'], str):
                        config['rotation'] = RotationTypes[config['rotation']].value
                    config.update(use_this_camera=True, exposure_mode='MANUAL', framerate=30.0)
            if exposure is not None:
                for config in configs.values():
                    config['exposure'] = exposure
            report['requested_configs'] = configs
            created = api.request('POST', '/skellycam/camera/group/apply', {'camera_configs': configs, 'backend': capture_backend})
            report['camera_group'] = created
            with StreamClient(api.server_url) as stream:
                stream.wait_for_state()
                stream.request_image_sizes(created['camera_configs'])
                stream.collect_frames(2.0)
                api.request('POST', '/skellycam/camera/group/all/record/start', {
                    'recording_name': 'capture-baseline', 'recording_directory': str((output_directory / 'recordings').resolve()), 'mic_device_index': -1})
                samples = stream.collect_frames(5.0)
                recordings = api.request('GET', '/skellycam/camera/group/all/record/stop')
                api.request('DELETE', '/skellycam/camera/group/close/all')
                report['recording_response'] = recordings
                report['recordings'] = [audit_recording(Path(recording['recording_path']), selected) for recording in recordings]
                report['stream'] = inspect_stream(samples, created['camera_configs'], output_directory, capture_backend)
                report['status'] = 'passed' if report['recordings'] and all(recording['passed'] for recording in report['recordings']) else 'failed'
                save_json(output_directory / 'baseline.json', report)
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = f'{type(error).__name__}: {error}'
        report['traceback'] = traceback.format_exc()
    finally:
        if session.owns_output_directory:
            save_json(output_directory / 'baseline.json', report)
    return report
