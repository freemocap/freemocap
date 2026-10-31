"""Own one test server; never kill an unrelated process or overwrite a prior run."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import psutil
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class ApiResponseError(RuntimeError):
    def __init__(self, status_code: int, response_body: str):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"HTTP {status_code}: {response_body}")


class ApiClient:
    def __init__(self, server_url: str, output_directory: Path):
        self.server_url = server_url.rstrip('/')
        self.output_directory = output_directory
        self.recording_active = False

    def request(self, method: str, route_path: str, request_body: dict | None = None, timeout_seconds: float = 90.0) -> object:
        started = time.perf_counter()
        status_code = 0
        response_text = ''
        try:
            request = Request(self.server_url + route_path, method=method,
                              data=None if request_body is None else json.dumps(request_body).encode(),
                              headers={'Content-Type': 'application/json'})
            try:
                with urlopen(request, timeout=timeout_seconds) as response:
                    status_code = response.status
                    response_text = response.read().decode('utf-8')
            except HTTPError as error:
                status_code = error.code
                response_text = error.read().decode('utf-8', errors='replace')
                raise ApiResponseError(status_code, response_text) from error
            if route_path.endswith('/record/start') or route_path.endswith('/recording/start'):
                self.recording_active = True
            elif route_path.endswith('/record/stop') or route_path.endswith('/recording/stop'):
                self.recording_active = False
            elif method == 'DELETE' and route_path.endswith('/group/close/all'):
                self.recording_active = False
            return json.loads(response_text) if response_text else None
        finally:
            with (self.output_directory / 'api-requests.jsonl').open('a', encoding='utf-8') as output:
                output.write(json.dumps({'method': method, 'path': route_path, 'request': request_body,
                                         'status': status_code, 'elapsed_seconds': time.perf_counter() - started,
                                         'response': response_text}) + '\n')


class ServerSession:
    def __init__(self, output_directory: Path):
        self.output_directory = output_directory.resolve()
        self.process = None
        self.log_output = None
        self.api_client = None
        self.cleanup_errors = []
        self.owns_output_directory = False
        self.server_pid = None

    def __enter__(self) -> ServerSession:
        self.output_directory.mkdir(parents=True, exist_ok=False)
        self.owns_output_directory = True
        from freemocap.tools.hardware_validation.provenance import capture_provenance
        (self.output_directory / 'provenance.json').write_text(json.dumps(capture_provenance(), indent=2), encoding='utf-8')
        data_directory = self.output_directory / 'data'
        data_directory.mkdir()
        (data_directory / 'telemetry_config.json').write_text('{"telemetry_enabled": false}', encoding='utf-8')
        with socket.socket() as port_socket:
            port_socket.bind(('127.0.0.1', 0))
            server_port = port_socket.getsockname()[1]
        self.api_client = ApiClient(f'http://127.0.0.1:{server_port}', self.output_directory)
        child_environment = os.environ.copy()
        child_environment.update(FREEMOCAP_BASE_FOLDER=str(self.output_directory / 'data'),
                                 SKELLYLOGS_LOG_DIR=str(self.output_directory / 'logs'),
                                 PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
        self.log_output = (self.output_directory / 'server.log').open('w', encoding='utf-8')
        try:
            self.process = subprocess.Popen(
                [sys.executable, '-B', '-m', 'freemocap', '--port', str(server_port),
                 '--route-inventory', str(self.output_directory / 'route-inventory.json')],
                env=child_environment, stdout=self.log_output, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(f'Test server exited during startup; inspect {self.output_directory / "server.log"}')
                try:
                    health = self.api_client.request('GET', '/health', timeout_seconds=1.0)
                    candidate_pid = health.get('pid')
                    if not self.owns_server_pid(candidate_pid):
                        raise RuntimeError('Selected port responded from an unrelated process; refusing to control it')
                    self.server_pid = candidate_pid
                    return self
                except (OSError, ApiResponseError):
                    time.sleep(0.2)
            raise TimeoutError('Test server failed to become healthy within 90 seconds')
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        cleanup_errors = []
        if self.process is not None and self.process.poll() is None:
            cleanup_routes = []
            if self.server_pid is not None:
                try:
                    health = self.api_client.request('GET', '/health', timeout_seconds=1.0)
                    if health.get('pid') == self.server_pid and self.owns_server_pid(self.server_pid):
                        cleanup_routes = [('DELETE', '/freemocap/mocap/realtime/pipelines'),
                                       ('DELETE', '/skellycam/camera/group/close/all'), ('GET', '/shutdown')]
                except Exception as error:
                    cleanup_errors.append(f'Cannot verify owned server before cleanup: {error}')
            if cleanup_routes and self.api_client.recording_active:
                cleanup_routes.insert(0, ('GET', '/skellycam/camera/group/all/record/stop'))
            for method, route_path in cleanup_routes:
                try:
                    self.api_client.request(method, route_path, timeout_seconds=20.0)
                except Exception as error:
                    cleanup_errors.append(f'{route_path}: {error}')
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                # Only terminate the exact child owned by this session, never a port/PID search.
                cleanup_errors.append('Graceful server shutdown timed out; terminated the owned server')
                try:
                    descendants = psutil.Process(self.process.pid).children(recursive=True)
                    for descendant in reversed(descendants):
                        try:
                            descendant.terminate()
                        except psutil.NoSuchProcess:
                            pass
                    psutil.wait_procs(descendants, timeout=5)
                except psutil.NoSuchProcess:
                    pass
                self.process.terminate()
                self.process.wait(timeout=10)
        if self.log_output is not None:
            self.log_output.close()
        if self.process is not None and self.process.poll() not in (0, None):
            cleanup_errors.append(f'Server exit code: {self.process.returncode}')
        (self.output_directory / 'server-cleanup.json').write_text(json.dumps({
            'exit_code': None if self.process is None else self.process.poll(),
            'errors': cleanup_errors,
        }, indent=2), encoding='utf-8')
        self.cleanup_errors = cleanup_errors

    def owns_server_pid(self, candidate_pid: int | None) -> bool:
        if candidate_pid is None or self.process is None or self.process.poll() is not None:
            return False
        try:
            return candidate_pid == self.process.pid or any(
                parent.pid == self.process.pid for parent in psutil.Process(candidate_pid).parents())
        except psutil.NoSuchProcess:
            return False

    def __exit__(self, exception_type, exception, traceback):
        self.close()
        if self.cleanup_errors:
            if exception is not None:
                exception.add_note('; '.join(self.cleanup_errors))
            else:
                raise RuntimeError('Server cleanup failed: ' + '; '.join(self.cleanup_errors))
