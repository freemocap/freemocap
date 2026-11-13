"""Replay through RustCameraGroup, its pixel worker, Core workers and matched frame lookup.

The fake replaces the native device/frameset interface. Frame numbers start late and
skip so that an implementation using sequential array indices cannot pass.
"""
import asyncio
import multiprocessing
import threading
import time
from contextlib import ExitStack
import cbor2
import cv2
import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.rust_camera_group import RustCameraGroup
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.realtime.capture_group import CaptureGroup
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.tests.reference_paths import recordings_root
from fastapi import FastAPI, WebSocket
from unittest.mock import AsyncMock, Mock
from freemocap.api.websocket import websocket_server
from freemocap.app.freemocap_application import FreemocapApplication
from freemocap.core.pipeline.realtime.startup_status import RealtimeStartupStatus


class ReplayFrameset:
    def __init__(self, number, images):
        self.frame_number = number
        self.images = images
        self.start = time.perf_counter_ns()

    def cameras(self):
        return {key: dict(width=image.shape[1], height=image.shape[0],
                          loop_start_ns=self.start, frame_available_ns=self.start + 10)
                for key, image in self.images.items()}

    def decode_into(self, targets):
        for key, image in self.images.items():
            np.copyto(targets[key], image)


class ReplayDevice:
    latest = None

    def newest_frameset(self, group_id, cursor):
        latest = self.latest
        return latest if latest.frame_number > cursor else None

    def close_group(self, group_id):
        pass


@pytest.mark.parametrize(("reference", "continuous"), [(False, False), (True, False), (True, True)],
                         ids=["synthetic", "reference-video", "reference-video-60fps"])
def test_rust_group_delivers_successive_processed_frames(reference, continuous, monkeypatch):
    with ExitStack() as cleanup:
        readers = {}
        if reference:
            directory = recordings_root() / "freemocap_test_data" / "synchronized_videos"
            paths = sorted(directory.glob("*.mp4"))
            if not paths:
                pytest.skip(f"Missing reference videos in {directory}")
            for index, path in enumerate(paths):
                reader = cv2.VideoCapture(str(path))
                cleanup.callback(reader.release)
                readers[str(index)] = reader

        def frames(number):
            images = {}
            if reference:
                for key, reader in readers.items():
                    ok, image = reader.read()
                    assert ok
                    images[key] = image
            else:
                images = {str(i): np.full((64, 96, 3), number + i, np.uint8) for i in range(2)}
            return ReplayFrameset(number, images)

        device = ReplayDevice()
        device.latest = frames(41)
        configs = {key: CameraConfig(camera_id=key, camera_index=int(key),
                                     resolution=dict(width=image.shape[1], height=image.shape[0]))
                   for key, image in device.latest.images.items()}
        group = RustCameraGroup("replay", configs, device)
        cleanup.callback(lambda: asyncio.run(group.close()))
        flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.THREAD)
        cleanup.callback(registry.shutdown_all)
        registry.start_heartbeat()
        service = InferenceService(worker_registry=registry)
        cleanup.callback(service.close)
        service.start()
        manager = RealtimePipelineManager(worker_registry=registry, inference_service=service)
        cleanup.callback(manager.shutdown)
        capture = CaptureGroup(group, flag)
        config = RealtimePipelineConfig(camera_node_config=dict(
            worker_mode=WorkerMode.PROCESS if reference else WorkerMode.THREAD,
            charuco_tracking_enabled=True, skeleton_tracking_enabled=reference),
            aggregator_config=dict(triangulation_enabled=False, skeleton_fitting_enabled=False),
            use_centralized_inference=reference, log_pipeline_times=False)
        pipeline = manager.create_pipeline(camera_group=capture, pipeline_config=config)
        app = FreemocapApplication.__new__(FreemocapApplication)
        app.realtime_pipeline_manager = manager
        app.inference_service = service
        app.startup_status = RealtimeStartupStatus()
        app.camera_group_manager = Mock()
        app.camera_group_manager.get_latest_frontend_payloads.return_value = {}
        monkeypatch.setattr(websocket_server, "get_freemocap_app", lambda: app)
        api = FastAPI()
        api.state.global_kill_flag = flag
        api.state.log_relay = None
        send = AsyncMock()
        socket = WebSocket(scope={"type": "websocket", "query_string": b""},
                           receive=AsyncMock(return_value={"type": "websocket.connect"}), send=send)
        loop = cleanup.enter_context(asyncio.Runner())
        loop.run(socket.accept())
        server = websocket_server.WebsocketServer(api, socket)
        cursor = -1
        tracked = []
        if continuous:
            # Exercise ring eviction during inference at the reported camera cadence.
            stop = threading.Event()
            images = device.latest.images

            def publish():
                start = time.monotonic()
                while not stop.is_set():
                    elapsed = time.monotonic() - start
                    tick = int(elapsed * 60)
                    device.latest = ReplayFrameset(41 + tick, images)
                    stop.wait(max(0, (tick + 1) / 60 - elapsed))

            producer = threading.Thread(target=publish)
            producer.start()
            cleanup.callback(producer.join)
            cleanup.callback(stop.set)
        for number in (41, 43, 48, 55):
            if cursor >= 0 and not continuous:
                device.latest = frames(number)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                assert pipeline.alive, pipeline.failure
                context = loop.run(server._await_next_frame())
                if context is not None and context.aggregator_output is not None:
                    output = context.aggregator_output
                    break
                if reference and not continuous and number == 41 and service.has_result(pipeline.id) and pipeline._latest_aggregation_output is not None:
                    # Cold inference may miss the aggregator's first-frame deadline.
                    break
                time.sleep(0.005)
            else:
                pytest.fail(f"No processed frame {number} after {cursor}, pixel head {capture.shm.latest_multiframe_number}")
            if continuous:
                assert output.frame_number > cursor
                number = output.frame_number
            cursor = number
            if context is None or context.aggregator_output is None:
                continue
            assert output.frame_number == number
            assert set(output.camera_node_outputs) == set(configs)
            assert all(camera.frame_number == number for camera in output.camera_node_outputs.values())
            if any(camera.skeleton_observation is not None for camera in output.camera_node_outputs.values()):
                tracked.append(number)
            assert context.image_payload is not None and len(context.image_payload) > 0
            loop.run(server._relay._send_frame(context))
            wire = cbor2.loads(send.await_args.args[0]["bytes"])
            assert wire["frame_number"] == number and wire["image"] == bytes(context.image_payload)
            if number in tracked:
                assert wire["trackers"]
        if reference:
            assert len(tracked) >= 2, f"Expected repeated skeleton tracking results, received {tracked}"
