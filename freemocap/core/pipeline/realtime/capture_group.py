"""Adapt capture implementations to core's multiprocessing frame transport.

SkellyCam owns capture and recording; core owns the transport its workers consume.
Native snapshots retain capture timestamps while transport frame indices are local
and contiguous. [@skellycamRustCapture2026]
"""
import logging
import threading
import time
from types import SimpleNamespace
import numpy as np

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.rust_camera_group import RustCameraGroup
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.frontend_payload_bytearray import create_frontend_payload

logger = logging.getLogger(__name__)


class CaptureGroup:
    """A pipeline view of a capture group; closing it never closes capture."""

    def __init__(self, source: CameraGroup | RustCameraGroup, global_kill_flag):
        self._source = source
        self.ipc = SimpleNamespace(global_kill_flag=global_kill_flag)
        self._owns_transport = isinstance(source, RustCameraGroup)
        self._stop = threading.Event()
        self._thread = None
        self._signature = None
        self._native_frames = {}
        self._transport_frames = {}
        self._sequence = 0
        self.error: str | None = None
        self._closed = False
        if not self._owns_transport:
            self.shm = source.shm
            return
        deadline = time.monotonic() + 5
        frames = source.get_latest_frames(frame_buffers=self._native_frames)
        while not frames and time.monotonic() < deadline:
            time.sleep(0.01)
            frames = source.get_latest_frames(frame_buffers=self._native_frames)
        if not frames or set(frames) != set(source.camera_ids):
            raise RuntimeError("The camera group did not provide a complete initial frame")
        configs = {}
        for camera_id, frame in frames.items():
            config = source.configs[camera_id]
            height, width, _ = frame.image[0].shape
            configs[camera_id] = config.model_copy(update={
                "resolution": type(config.resolution)(width=width, height=height),
            })
        self.shm = CameraGroupSharedMemory.create(configs, TimebaseMapping())
        try:
            self._publish(frames)
            self._thread = threading.Thread(target=self._relay, name="CaptureFrameRelay", daemon=True)
            self._thread.start()
        except BaseException:
            self.shm.unlink_and_close()
            raise

    @property
    def id(self):
        return self._source.id

    @property
    def camera_ids(self):
        return self._source.camera_ids

    @property
    def configs(self):
        return self._source.configs

    @property
    def started(self):
        return True if self._owns_transport else self._source.started

    def start(self):
        if not self._owns_transport:
            self._source.start()

    def _publish(self, frames):
        if set(frames) != set(self.camera_ids):
            return
        signature = tuple((key, int(frames[key].frame_metadata.frame_number[0]),
                           int(frames[key].frame_metadata.timestamps.pre_frame_grab_ns[0]))
                          for key in sorted(frames))
        if signature == self._signature:
            return
        # Validate the entire set before advancing any ring buffer.
        for camera_id, frame in frames.items():
            if frame.dtype != self.shm.camera_shms[camera_id].dtype:
                raise RuntimeError("Camera image dimensions changed; restart realtime processing")
        for camera_id, original in frames.items():
            frame = self._transport_frames.get(camera_id)
            if frame is None:
                frame = np.zeros_like(original)
                self._transport_frames[camera_id] = frame
            np.copyto(frame, original)
            frame.frame_metadata.frame_number = self._sequence
            # Keep the camera identity and rotation carried by this frame. The
            # settings used to allocate transport can be older than a live update.
            self.shm.camera_shms[camera_id].put_frame(frame, overwrite=True)
        self._signature = signature
        self._sequence += 1

    def _relay(self):
        try:
            while not self._stop.is_set() and not self.ipc.global_kill_flag.value:
                if not self._source.cameras.all_ready:
                    raise RuntimeError("The capture group closed during realtime processing")
                cursor = max(item[1] for item in self._signature) if self._signature else -1
                frames = self._source.get_latest_frames(if_newer_than=cursor, frame_buffers=self._native_frames)
                if frames:
                    self._publish(frames)
                self._stop.wait(0.005)
        except Exception as error:
            self.error = str(error)
            logger.exception("Camera frame relay failed")

    def close_transport(self):
        if self._closed:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("Camera frame relay did not stop")
        if self._owns_transport:
            self.shm.unlink_and_close()
        self._closed = True

    async def update_camera_settings(self, requested_configs):
        return await self._source.update_camera_settings(requested_configs)

    async def pause_unpause(self):
        await self._source.pause_unpause()

    def get_frontend_payload_by_frame_number(self, frame_number, display_image_sizes=None):
        if not self._owns_transport:
            return self._source.get_frontend_payload_by_frame_number(frame_number, display_image_sizes)
        if self._closed or frame_number > self.shm.latest_multiframe_number:
            return None
        frames = {key: ring.get_data_by_index(index=frame_number, rec_array=None)
                  for key, ring in self.shm.camera_shms.items()}
        if any(int(frame.frame_metadata.frame_number[0]) != frame_number for frame in frames.values()):
            return None
        _, timestamp, payload = create_frontend_payload(latest_frames=frames, display_image_sizes=display_image_sizes)
        return payload, float(timestamp)
