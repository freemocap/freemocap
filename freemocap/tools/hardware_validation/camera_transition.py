"""Compare camera identity and orientation across raw/tracked/raw WebSocket output.

Run with ``python -m freemocap.tools.hardware_validation.camera_transition
--output <new-directory> --backend rust --recording-info <json> --calibration <toml>``.
The camera scene should remain reasonably still during the comparison.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import time
import traceback

import cv2
import numpy as np
from skellycam.core.camera.config.image_rotation_types import RotationTypes

from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.tools.hardware_validation.frame_checks import decode_image_payload, timing_metrics
from freemocap.tools.hardware_validation.hardware_run import save_json
from freemocap.tools.hardware_validation.server_session import ServerSession
from freemocap.tools.hardware_validation.stream_client import StreamClient


def capture_phase(stream, output_directory, phase_name, tracked):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        stream.wait_for_frames(timeout_seconds=30.0)
        samples = stream.collect_frames(3.0)
        if all(bool(message.get('trackers')) == tracked for _, message in samples):
            break
    else:
        raise TimeoutError(f'No stable {phase_name} image stream')
    images = {image.camera_id: image for image in decode_image_payload(samples[-1][1]['image'])}
    for identity, image in images.items():
        cv2.imwrite(str(output_directory / f'{phase_name}-{identity}.jpg'), image.image_pixels)
    summary = {'cameras': {identity: {'camera_index': image.camera_index,
                'image_shape': list(image.image_pixels.shape)} for identity, image in images.items()},
        'delivery': timing_metrics(np.asarray([received for received, _ in samples]),
                                   np.asarray([message['frame_number'] for _, message in samples]))}
    return images, summary


def compare_phases(reference_images, candidate_images):
    def thumbnail(image):
        return cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (96, 96)).astype(np.float32).ravel()

    assert reference_images.keys() == candidate_images.keys(), 'Camera identities changed'
    results = {}
    for identity, candidate in candidate_images.items():
        reference = reference_images[identity]
        expected_height, expected_width = reference.image_pixels.shape[:2]
        height, width = candidate.image_pixels.shape[:2]
        scores = {}
        for reference_id, source in reference_images.items():
            for rotation in (-1, 0, 1, 2):
                pixels = source.image_pixels if rotation == -1 else cv2.rotate(source.image_pixels, rotation)
                reference_values, candidate_values = thumbnail(pixels), thumbnail(candidate.image_pixels)
                scores[f'{reference_id}:{rotation}'] = (float(np.corrcoef(reference_values, candidate_values)[0, 1])
                    if reference_values.std() > 0 and candidate_values.std() > 0 else 0.0)
        best_match = max(scores, key=scores.get)
        results[identity] = {'correlations': scores, 'best_match': best_match,
            'passed': bool(candidate.camera_index == reference.camera_index
                and height * expected_width == width * expected_height
                and best_match == f'{identity}:-1' and scores[best_match] > 0.8)}
    return results


def run_transition(output_directory, backend, recording_info, calibration):
    report = {'backend': backend, 'status': 'failed', 'phases': {}, 'comparisons': {}}
    session = ServerSession(output_directory)
    try:
        with session:
            api = session.api_client
            configs = json.loads(recording_info.read_text(encoding='utf-8'))['camera_configs']
            for config in configs.values():
                if isinstance(config['rotation'], str):
                    config['rotation'] = RotationTypes[config['rotation']].value
                config.update(exposure=-5, exposure_mode='MANUAL', framerate=30.0)
            calibration_directory = output_directory / 'data' / 'calibrations'
            calibration_directory.mkdir(exist_ok=True)
            shutil.copyfile(calibration, calibration_directory / 'last_successful_camera_calibration.toml')
            api.request('POST', '/skellycam/camera/group/apply', {'camera_configs': configs, 'backend': backend})
            with StreamClient(api.server_url) as stream:
                stream.request_image_sizes(configs)
                original, report['phases']['raw_before'] = capture_phase(stream, output_directory, 'raw_before', False)
                assert original.keys() == configs.keys(), 'Not every requested camera produced images'
                assert all(image.camera_index == configs[identity]['camera_index']
                           for identity, image in original.items()), 'Camera device indices differ from the request'
                configuration = RealtimePipelineConfig()
                configuration.skeleton_inference_node_config.execution_provider = 'cuda'
                api.request('POST', '/freemocap/realtime/apply', {'cameraConfigs': None, 'realtimeCameraIds': None,
                    'realtimeConfig': configuration.model_dump(mode='json', exclude_computed_fields=True)},
                    timeout_seconds=180.0)
                processed, report['phases']['tracked'] = capture_phase(stream, output_directory, 'tracked', True)
                report['comparisons']['tracked'] = compare_phases(original, processed)
                api.request('DELETE', '/freemocap/mocap/realtime/pipelines')
                restored, report['phases']['raw_after'] = capture_phase(stream, output_directory, 'raw_after', False)
                report['comparisons']['raw_after'] = compare_phases(original, restored)
            assert all(result['passed'] for phase in report['comparisons'].values() for result in phase.values()), (
                'Camera identity/orientation comparison failed; inspect saved images and correlations')
            report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', error=str(error), traceback=traceback.format_exc())
    finally:
        if session.owns_output_directory:
            save_json(output_directory / 'transition-report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--backend', choices=('python', 'rust'), required=True)
    parser.add_argument('--recording-info', type=Path, required=True)
    parser.add_argument('--calibration', type=Path, required=True)
    arguments = parser.parse_args()
    result = run_transition(arguments.output.resolve(), arguments.backend, arguments.recording_info, arguments.calibration)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] == 'passed' else 1)
