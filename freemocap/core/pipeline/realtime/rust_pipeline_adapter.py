"""
RustRealtimePipeline: thin adapter around _freemocap_rust.PyPipeline.

The backend decision (Rust vs Python) is made by RealtimePipelineManager,
not here. This class is a simple wrapper with no backend flag.

When USE_RUST_BACKEND=True, the manager creates this instead of the
Python RealtimePipeline. This adapter never touches .shm, .ipc, .started,
or .start() on the camera_group — those are Python-only concepts.
"""
import logging
import os
import uuid
from typing import Optional

from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt
from freemocap.core.viz.frontend_payload import FrontendImagePacket, FrontendPayload

logger = logging.getLogger(__name__)

_native = None


def _get_native():
    """Lazy-import _freemocap_rust with OpenCV DLL discovery."""
    global _native
    if _native is not None:
        return _native

    # OpenCV DLL discovery (same pattern as skellytracker)
    opencv_bin = "C:/tools/opencv/build/x64/vc16/bin"
    if os.path.isdir(opencv_bin):
        os.add_dll_directory(opencv_bin)

    import _freemocap_rust

    _native = _freemocap_rust
    return _native


class RustRealtimePipeline:
    """
    Wraps _freemocap_rust.PyPipeline.

    Extracts FrameSlots from the skellycam PyO3 CameraGroupManager
    at construction time. Frame data never passes through Python —
    the distributor polls the CameraGroup's Arc slots directly in Rust.
    """

    def __init__(
        self,
        *,
        camera_group,
        pipeline_config,
        realtime_camera_ids: list[str] | None = None,
    ):
        self._id: PipelineIdString = str(uuid.uuid4())[:6]
        self._camera_group = camera_group

        cam_ids = realtime_camera_ids or list(camera_group.configs.keys())
        native = _get_native()

        config_json = pipeline_config.model_dump_json()

        # camera_group._native is the _skellycam_rust.CameraGroupManager singleton.
        # camera_group.id is the group_id string returned from create_or_update_group.
        # PyPipeline.__init__ extracts FrameSlots from this internally (Rust-to-Rust).
        self._inner = native.PyPipeline(
            camera_group._native,
            camera_group.id,
            config_json,
            cam_ids,
        )

        logger.info(
            "Created RustRealtimePipeline [%s] for camera group [%s] with cameras %s",
            self._id,
            camera_group.id,
            cam_ids,
        )

    # ── Properties matching RealtimePipeline interface ────────────────────

    @property
    def id(self) -> PipelineIdString:
        return self._id

    @property
    def camera_group(self):
        return self._camera_group

    @property
    def camera_ids(self) -> list[str]:
        return self._inner.camera_ids()

    @property
    def camera_group_id(self) -> str:
        return self._camera_group.id

    @property
    def alive(self) -> bool:
        return self._inner.alive()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        logger.info("Starting RustRealtimePipeline [%s]", self._id)
        self._inner.start()

    def shutdown(self) -> None:
        logger.info("Shutting down RustRealtimePipeline [%s]", self._id)
        self._inner.shutdown()

    # ── Config ────────────────────────────────────────────────────────────

    def update_config(self, new_config) -> None:
        self._inner.update_config(new_config.model_dump_json())

    # ── Frontend payload ──────────────────────────────────────────────────

    def get_latest_frontend_payload(
        self, if_newer_than: FrameNumberInt
    ) -> Optional[FrontendImagePacket]:
        output = self._inner.get_latest_output()
        if output is None:
            return None

        frame_number = output["frame_number"]
        if frame_number <= if_newer_than:
            return None

        return FrontendImagePacket(
            images_bytearray=bytearray(output.get("frontend_payload", b"")),
            multiframe_timestamp=output.get("timestamp_ns", 0.0),
            frontend_payload=FrontendPayload(
                frame_number=frame_number,
                camera_group_id=self.camera_group_id,
            ),
        )
