"""Native MPEG-4 playback uses bounded binary delivery and scoped cleanup."""

import multiprocessing
import tempfile
import unittest
from pathlib import Path

import av
import cbor2
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.types.frontend_payload_bytearray import FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE, FRONTEND_FRAME_HEADER_DTYPE

from freemocap.api.websocket.playback_socket import playback_socket_router
from freemocap.api.http.playback.playback_router import VideoSourceInfo, preferred_video_source
from freemocap.core.playback.media_selection import PlaybackVideoSource, discover_video_paths, video_source_folder


class PlaybackSocketTests(unittest.TestCase):
    def test_annotated_is_preferred_with_raw_fallback(self) -> None:
        available = VideoSourceInfo(available=True, valid=True, video_count=1)
        missing = VideoSourceInfo(available=False, valid=False, video_count=0)
        self.assertEqual(preferred_video_source(synchronized=available, annotated=available), PlaybackVideoSource.ANNOTATED)
        self.assertEqual(preferred_video_source(synchronized=available, annotated=missing), PlaybackVideoSource.SYNCHRONIZED)

    def test_root_media_discovery_keeps_matching_stems(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            recording = Path(temporary)
            for name in ("view.mp4", "view.avi", "notes.txt"):
                (recording / name).touch()
            folder = video_source_folder(recording=recording, source=PlaybackVideoSource.SYNCHRONIZED)
            self.assertEqual(folder, recording)
            self.assertEqual(tuple(path.name for path in discover_video_paths(folder=folder)), ("view.avi", "view.mp4"))

    def test_mpeg4_group_seek_and_close(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "recording" / "synchronized_videos"
            folder.mkdir(parents=True)
            for name in ("arbitrary long camera filename A.mp4", "another view B.mp4"):
                with av.open(str(folder / name), mode="w") as container:
                    stream = container.add_stream("mpeg4", rate=6)
                    stream.width = 64
                    stream.height = 48
                    stream.pix_fmt = "yuv420p"
                    for value in (20, 60, 100):
                        frame = av.VideoFrame.from_ndarray(np.full((48, 64, 3), value, dtype=np.uint8), format="rgb24")
                        for packet in stream.encode(frame):
                            container.mux(packet)
                    for packet in stream.encode():
                        container.mux(packet)
            global_flag = multiprocessing.Value("b", False)
            registry = WorkerRegistry(global_kill_flag=global_flag, worker_mode=WorkerMode.THREAD)
            app = FastAPI()
            app.state.worker_registry = registry
            app.include_router(playback_socket_router)
            with TestClient(app) as client:
                with client.websocket_connect(f"/websocket/playback/recording?recording_parent_directory={temporary}") as socket:
                    socket.send_json({"source": "synchronized", "encoded_group_bytes": 100000})
                    ready = cbor2.loads(socket.receive_bytes())
                    self.assertEqual(ready["kind"], "playback_ready", ready)
                    self.assertEqual(ready["frame_count"], 3)
                    self.assertEqual(len(ready["filenames"]), 2)
                    socket.send_json({"command": "range", "payload": {"generation": 1, "start_frame": 0, "end_frame": 2, "encoding": {"scale": 1.0, "jpeg_quality": 90}}})
                    for ordinal in (0, 1):
                        frame = cbor2.loads(socket.receive_bytes())
                        self.assertEqual(frame["frame_number"], ordinal)
                        header = np.frombuffer(frame["image"], dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE, count=1)[0]
                        self.assertEqual(header["number_of_cameras"], 2)
                        self.assertEqual(header["frame_number"], ordinal)
                        camera = np.frombuffer(frame["image"], dtype=FRONTEND_FRAME_HEADER_DTYPE, count=1,
                            offset=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE.itemsize)[0]
                        self.assertEqual((camera["image_width"], camera["image_height"]), (64, 48))
                    self.assertEqual(cbor2.loads(socket.receive_bytes())["kind"], "playback_end")
                    socket.send_json({"command": "range", "payload": {"generation": 2, "start_frame": 0, "end_frame": 1, "encoding": {"scale": 0.5, "jpeg_quality": 60}}})
                    frame = cbor2.loads(socket.receive_bytes())
                    self.assertEqual((frame["generation"], frame["frame_number"]), (2, 0))
                    camera = np.frombuffer(frame["image"], dtype=FRONTEND_FRAME_HEADER_DTYPE, count=1,
                        offset=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE.itemsize)[0]
                    self.assertEqual((camera["image_width"], camera["image_height"]), (32, 24))
                    self.assertEqual(cbor2.loads(socket.receive_bytes())["kind"], "playback_end")
                    socket.send_json({"command": "close", "payload": {}})
                    socket.receive()
                with client.websocket_connect(f"/websocket/playback/recording?recording_parent_directory={temporary}") as socket:
                    socket.send_json({"source": "synchronized", "encoded_group_bytes": 100000})
                    self.assertEqual(cbor2.loads(socket.receive_bytes())["kind"], "playback_ready")
            self.assertFalse(global_flag.value)
            self.assertFalse(any(worker.is_alive() for worker in registry._workers))
            self.assertEqual(len(list(folder.iterdir())), 2)
