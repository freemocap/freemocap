"""A realtime pipeline's view of a SkellyCam camera group.

SkellyCam owns capture, recording and the shared memory that either camera backend fills with its frames, at
SkellyCam frame numbers (frame N at ring index N). Core's realtime workers read that memory directly; this view
never copies, renumbers or closes capture.
"""
import logging
from types import SimpleNamespace

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.rust_camera_group import RustCameraGroup

logger = logging.getLogger(__name__)


class CaptureGroup:
    """A pipeline view of a capture group; closing it never closes capture."""

    def __init__(self, source: CameraGroup | RustCameraGroup, global_kill_flag):
        self._source = source
        self.ipc = SimpleNamespace(global_kill_flag=global_kill_flag)
        self.shm = source.shm
        self._closed = False

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
        return self._source.started

    @property
    def error(self) -> str | None:
        """Why the group stopped delivering frames into shared memory, if it did."""
        return self._source.transport_error

    def start(self):
        self._source.start()

    def close_transport(self):
        """End this pipeline's use of the camera group; the group keeps its shared memory."""
        self._closed = True

    async def update_camera_settings(self, requested_configs):
        return await self._source.update_camera_settings(requested_configs)

    async def pause_unpause(self):
        await self._source.pause_unpause()

    def get_frontend_payload_by_frame_number(self, frame_number, display_image_sizes=None):
        if self._closed:
            return None
        return self._source.get_frontend_payload_by_frame_number(frame_number, display_image_sizes)
