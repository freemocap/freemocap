"""Read production CBOR messages without rendering a UI or acknowledging fake FPS."""
from __future__ import annotations

import time
import json
from collections import deque
from threading import Condition, Thread

import cbor2
from skellycam.core.camera.config.camera_config import CameraConfig
from websockets.sync.client import connect


class StreamClient:
    def __init__(self, server_url: str, compression: str | None = 'deflate'):
        self.socket = connect(server_url.replace('http://', 'ws://') + '/websocket/connect?connection_id=hardware-validation',
                              max_size=64 * 1024 * 1024, compression=compression)
        self.condition = Condition()
        self.messages = deque(maxlen=180)
        self.app_state = None
        self.state_history = deque(maxlen=128)
        self.failure = None
        self.closed = False
        self.message_count = 0
        self.frame_count = 0
        self.thread = Thread(target=self._receive_messages, name='HardwareStreamReader', daemon=True)
        self.thread.start()

    def _receive_messages(self):
        try:
            for payload in self.socket:
                if isinstance(payload, str):
                    if payload.startswith('ping'):
                        self.socket.send('pong')
                    continue
                message = cbor2.loads(payload)
                with self.condition:
                    self.message_count += 1
                    if message['kind'] == 'app_state':
                        self.app_state = message['state']
                        self.state_history.append(message)
                    elif message['kind'] == 'frame':
                        self.frame_count += 1
                        self.messages.append((time.perf_counter(), message))
                    self.condition.notify_all()
        except Exception as error:
            if not self.closed:
                self.failure = error
                with self.condition:
                    self.condition.notify_all()

    def wait_for_state(self, timeout_seconds: float = 10.0) -> dict:
        with self.condition:
            ready = self.condition.wait_for(lambda: self.app_state is not None or self.failure is not None,
                                            timeout_seconds)
            if self.failure is not None:
                raise RuntimeError('WebSocket reader failed') from self.failure
            if not ready:
                raise TimeoutError('No application state received')
            return self.app_state

    def close(self):
        self.closed = True
        self.socket.close()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError('WebSocket reader did not stop')

    def collect_frames(self, duration_seconds: float) -> list:
        started = time.perf_counter()
        deadline = started + duration_seconds
        with self.condition:
            while time.perf_counter() < deadline and self.failure is None:
                self.condition.wait(timeout=max(0.0, deadline - time.perf_counter()))
            if self.failure is not None:
                raise RuntimeError('WebSocket reader failed') from self.failure
            samples = [(received, message) for received, message in self.messages if received >= started]
        if len(samples) < 3:
            raise TimeoutError(f'Only {len(samples)} image messages received in {duration_seconds} seconds')
        return samples

    def request_image_sizes(self, camera_configs: dict) -> None:
        sizes = {}
        for camera_id, config in camera_configs.items():
            width, height = config['resolution']['width'], config['resolution']['height']
            if CameraConfig.model_validate(config).rotation.value in (0, 2):
                width, height = height, width
            sizes[camera_id] = {'width': width, 'height': height}
        self.socket.send(json.dumps({'frameNumber': 0, 'displayImageSizes': sizes}))

    def wait_for_frames(self, minimum_count: int = 3, timeout_seconds: float = 8.0) -> None:
        with self.condition:
            target_count = self.frame_count + minimum_count
            available = self.condition.wait_for(lambda: self.frame_count >= target_count or self.failure is not None, timeout_seconds)
            if self.failure is not None:
                raise RuntimeError('WebSocket reader failed') from self.failure
            if not available:
                raise TimeoutError(f'No fresh camera frames within {timeout_seconds} seconds')

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.close()
