"""Bounded physical-camera scenarios, with independent result files for every case."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import time
import traceback

import numpy as np
from skellycam.core.camera.config.camera_config import CameraConfig

from freemocap.tools.hardware_validation.frame_checks import audit_recording, brightness_response, decode_image_payload, orientation_response
from freemocap.tools.hardware_validation.hardware_run import inspect_stream, make_camera_configs, save_json
from freemocap.tools.hardware_validation.server_session import ApiResponseError, ServerSession
from freemocap.tools.hardware_validation.stream_client import StreamClient
from freemocap.tools.hardware_validation.suite_plan import SuiteCase, selected_cases
from freemocap.tools.hardware_validation.route_coverage import write_route_coverage


class SuiteRunner:
    def __init__(self, session: ServerSession, backend: str, camera_devices: list):
        self.session = session
        self.api = session.api_client
        self.backend = backend
        self.devices = camera_devices
        self.configs = {}
        self.stream = None

    def close_cameras(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None
        self.api.request('DELETE', '/skellycam/camera/group/close/all', timeout_seconds=15.0)
        self.configs = {}

    def apply_configs(self, configs: dict, backend: str | None = None) -> dict:
        response = self.api.request('POST', '/skellycam/camera/group/apply', {
            'backend': self.backend if backend is None else backend, 'camera_configs': configs}, timeout_seconds=45.0)
        self.configs = response['camera_configs']
        return response

    def ensure_cameras(self, camera_ids: tuple[str, ...]):
        if set(self.configs) != set(camera_ids):
            if self.configs or self.stream is not None:
                self.close_cameras()
            self.apply_configs(make_camera_configs(self.devices, camera_ids))
        if self.stream is None:
            self.stream = StreamClient(self.api.server_url)
            self.stream.wait_for_state()
            self.stream.request_image_sizes(self.configs)
            self.stream.collect_frames(1.0)

    def collect(self, case_directory: Path, duration_seconds: float = 1.0) -> tuple[list, dict]:
        self.stream.request_image_sizes(self.configs)
        # Discard frames queued before the setting acknowledgement.
        self.stream.wait_for_frames()
        samples = self.stream.collect_frames(duration_seconds)
        return samples, inspect_stream(samples, self.configs, case_directory, self.backend)

    def start_recording(self, case_directory: Path):
        self.api.request('POST', '/skellycam/camera/group/all/record/start', {
            'recording_name': 'capture', 'recording_directory': str(case_directory.resolve()), 'mic_device_index': -1}, timeout_seconds=15.0)

    def execute(self, case: SuiteCase, case_directory: Path, result: dict) -> dict:
        self.ensure_cameras(case.camera_ids)
        result['case'] = asdict(case)
        if case.case_name.startswith('record-'):
            self.start_recording(case_directory)
            samples = self.stream.collect_frames(5.0)
            recordings = self.api.request('GET', '/skellycam/camera/group/all/record/stop', timeout_seconds=20.0)
            result['recordings'] = [audit_recording(Path(recording['recording_path']), case.camera_ids) for recording in recordings]
            result['stream'] = inspect_stream(samples, self.configs, case_directory, self.backend)
            assert recordings and all(recording['passed'] for recording in result['recordings']), 'Recording failed capture/video checks'
        elif case.case_name in ('add-camera', 'remove-camera'):
            configs = make_camera_configs(self.devices, tuple(sorted(set(case.camera_ids) | set(case.requested_ids))))
            for identity, config in configs.items():
                config['use_this_camera'] = identity in case.requested_ids
            result['apply_response'] = self.apply_configs(configs)
            active = {identity: config for identity, config in self.configs.items() if config['use_this_camera']}
            assert set(active) == set(case.requested_ids), f'Applied membership {sorted(active)} differs from {case.requested_ids}'
            self.configs = active
            _, result['stream'] = self.collect(case_directory)
        elif case.case_name in ('pause-resume', 'pause-during-recording'):
            recording = case.case_name == 'pause-during-recording'
            if recording:
                self.start_recording(case_directory)
                self.stream.collect_frames(3.0)
            self.api.request('GET', '/skellycam/camera/group/all/pause_unpause', timeout_seconds=10.0)
            # A frame already in transport may arrive; verify the queue stops advancing after settling.
            time.sleep(0.4)
            with self.stream.condition:
                previous = self.stream.messages[-1][1]['sequence']
            time.sleep(0.6)
            with self.stream.condition:
                current = self.stream.messages[-1][1]['sequence']
            assert current == previous, 'Frames continued while camera group was paused'
            self.api.request('GET', '/skellycam/camera/group/all/pause_unpause', timeout_seconds=10.0)
            _, result['stream'] = self.collect(case_directory)
            if recording:
                result['recording_response'] = self.api.request('GET', '/skellycam/camera/group/all/record/stop', timeout_seconds=20.0)
        elif case.case_name == 'close-during-recording':
            self.start_recording(case_directory)
            self.stream.collect_frames(4.0)
            self.close_cameras()
            result['recording'] = audit_recording(case_directory / 'capture', case.camera_ids)
            assert result['recording']['passed'], 'Closing cameras left an incomplete recording'
        elif case.case_name == 'repeat-apply':
            before = self.apply_configs(deepcopy(self.configs))
            after = self.apply_configs(deepcopy(self.configs))
            assert before['group_id'] == after['group_id'], 'Identical apply unexpectedly recreated the camera group'
            _, result['stream'] = self.collect(case_directory)
        elif case.case_name == 'change-backend':
            destination = 'rust' if self.backend == 'python' else 'python'
            try:
                self.apply_configs(deepcopy(self.configs), destination)
            except ApiResponseError as error:
                assert error.status_code == 409, f'Expected explicit busy rejection, got {error.status_code}'
                result['busy_rejection'] = error.status_code
            else:
                raise AssertionError('Backend changed while cameras were active')
            self.close_cameras()
            previous_backend = self.backend
            self.backend = destination
            try:
                self.ensure_cameras(case.camera_ids)
                _, result['destination_stream'] = self.collect(case_directory)
                self.close_cameras()
            finally:
                self.backend = previous_backend
        elif case.case_name == 'disconnect-reconnect-stream':
            self.stream.close()
            self.stream = None
            self.ensure_cameras(case.camera_ids)
            _, result['stream'] = self.collect(case_directory)
        elif case.case_name == 'stop-without-recording':
            try:
                result['stop_response'] = self.api.request('GET', '/skellycam/camera/group/all/record/stop', timeout_seconds=3.0)
            except ApiResponseError as error:
                assert error.status_code == 409, f'Expected explicit idle rejection, got {error.status_code}'
            _, result['stream'] = self.collect(case_directory)
        elif case.case_name == 'repeat-record-start':
            self.start_recording(case_directory)
            self.stream.collect_frames(3.0)
            try:
                self.start_recording(case_directory)
            except ApiResponseError as error:
                assert error.status_code == 409, f'Expected explicit recording rejection, got {error.status_code}'
            result['recording_response'] = self.api.request('GET', '/skellycam/camera/group/all/record/stop', timeout_seconds=20.0)
            result['recording'] = audit_recording(case_directory / 'capture', case.camera_ids)
            assert result['recording']['passed'], 'Repeated start damaged the original recording'
        elif case.control_name:
            original = deepcopy(self.configs)
            before_samples, result['before'] = self.collect(case_directory)
            requested = deepcopy(original)
            target = case.requested_ids[0]
            changes = {'exposure': {'exposure': -5, 'exposure_mode': 'MANUAL'},
                       'rotation': {'rotation': 0},
                       'exposure-auto': {'exposure_mode': 'AUTO'},
                       'exposure-recommend': {'exposure_mode': 'RECOMMEND'},
                       'resolution': {'resolution': {'width': 640, 'height': 480}}}[case.control_name]
            requested[target].update(changes)
            result['apply_response'] = self.apply_configs(requested)
            for identity in set(original) - {target}:
                for name in ('exposure', 'exposure_mode', 'rotation', 'resolution'):
                    assert self.configs[identity][name] == original[identity][name], f'{name} changed on untargeted camera {identity}'
            for name, value in changes.items():
                if value != 'RECOMMEND':
                    canonical = CameraConfig.model_validate(requested[target]).model_dump(mode='json')
                    assert self.configs[target][name] == canonical[name], f'Requested {name} was not applied to {target}'
            after_samples, result['after'] = self.collect(case_directory)
            if case.control_name == 'exposure':
                result['brightness_response'] = brightness_response(np.asarray(result['before']['cameras'][target]['brightness_samples']),
                    np.asarray(result['after']['cameras'][target]['brightness_samples']), 1)
                assert result['brightness_response']['outcome'] == 'pass', 'Brightness change was not demonstrated'
            elif case.control_name == 'rotation':
                before = next(frame.image_pixels for frame in decode_image_payload(before_samples[-1][1]['image']) if frame.camera_id == target)
                after = next(frame.image_pixels for frame in decode_image_payload(after_samples[-1][1]['image']) if frame.camera_id == target)
                result['rotation_response'] = orientation_response(before, after, 0)
                assert result['rotation_response']['outcome'] == 'pass', 'Requested rotation was not demonstrated in pixels'
            self.apply_configs(original)
        else:
            raise ValueError(f'Unimplemented hardware case: {case.case_name}')
        assert all(value.get('continuity_passed', True) for value in result.values() if isinstance(value, dict)), 'Stream repeated source frames'
        return result


def run_suite(output_directory: Path, backend: str, suite_name: str, only_cases: tuple[str, ...] = ()) -> dict:
    report = {'backend': backend, 'suite': suite_name, 'cases': [], 'server_errors': []}
    runner = None
    session = ServerSession(output_directory)
    try:
        with session:
            devices = session.api_client.request('POST', '/skellycam/camera/detect')['cameras']
            save_json(output_directory / 'camera-inventory.json', devices)
            cases = selected_cases(tuple(device['camera_id'] for device in devices), suite_name)
            if only_cases:
                if not set(only_cases) <= {case.case_name for case in cases}:
                    raise ValueError('Requested case not present in this suite')
                cases = [case for case in cases if case.case_name in only_cases]
            save_json(output_directory / 'suite-plan.json', [asdict(case) for case in cases])
            runner = SuiteRunner(session, backend, devices)
            for case in cases:
                case_directory = output_directory / case.case_name
                case_directory.mkdir()
                started = time.perf_counter()
                result = {'case': asdict(case), 'status': 'failed'}
                try:
                    runner.execute(case, case_directory, result)
                    result['status'] = 'passed'
                except Exception as error:
                    result.update(error=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
                    try:
                        runner.close_cameras()
                    except Exception as cleanup_error:
                        result['recovery_error'] = str(cleanup_error)
                result['elapsed_seconds'] = time.perf_counter() - started
                if runner.stream is not None:
                    with runner.stream.condition:
                        result['observed_app_state'] = deepcopy(runner.stream.app_state)
                        save_json(case_directory / 'app-state-messages.json', list(runner.stream.state_history))
                save_json(case_directory / 'result.json', result)
                report['cases'].append(result)
                save_json(output_directory / 'suite-report.json', report)
                print(json.dumps({'backend': backend, 'case': case.case_name, 'status': result['status'], 'error': result.get('error')}), flush=True)
                if session.process.poll() is not None:
                    raise RuntimeError('Server exited during camera tests; remaining cases were not executed')
            if runner.stream is not None:
                runner.stream.close()
                runner.stream = None
    except Exception as error:
        report['server_errors'].append(f'{type(error).__name__}: {error}')
    report['passed'] = bool(report['cases']) and all(case['status'] == 'passed' for case in report['cases']) and not report['server_errors']
    if session.owns_output_directory:
        save_json(output_directory / 'suite-report.json', report)
        if (output_directory / 'route-inventory.json').exists():
            write_route_coverage(output_directory)
    return report
