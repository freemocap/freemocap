from types import SimpleNamespace

import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.rust_camera_group import RustCameraGroup
from skellycam.core.types.frame_dtype_factories import create_frame_dtype
from freemocap.core.pipeline.realtime.capture_group import CaptureGroup


class NativeSnapshots(RustCameraGroup):
    def __init__(self, rotated=False):
        config = CameraConfig(camera_id="0001", camera_index=0,
                              resolution={"width": 8, "height": 6})
        super().__init__("native", {"0001": config}, SimpleNamespace(list_groups=lambda: ["native"]))
        image_config = config.model_copy(update={"resolution": type(config.resolution)(width=6, height=8)}) if rotated else config
        self.frame = np.zeros(1, dtype=create_frame_dtype(image_config)).view(np.recarray)
        self.frame.frame_metadata.frame_number = 17
        self.frame.frame_metadata.timestamps.pre_frame_grab_ns = 123456
        self.frame.image[:] = 61

    def get_latest_frames(self):
        return {"0001": self.frame}


@pytest.mark.parametrize("rotated", [False, True])
def test_native_transport_preserves_pixels_and_timestamps_with_contiguous_indices(rotated):
    source = NativeSnapshots(rotated)
    capture = CaptureGroup(source, SimpleNamespace(value=False))
    capture._stop.set()
    capture._thread.join(timeout=2)
    assert capture.error is None
    try:
        first = capture.shm.get_latest_multiframe()["0001"]
        assert int(first.frame_metadata.frame_number[0]) == 0
        assert int(source.frame.frame_metadata.frame_number[0]) == 17
        assert int(first.frame_metadata.timestamps.pre_frame_grab_ns[0]) == 123456
        np.testing.assert_array_equal(first.image, source.frame.image)
        source.frame.frame_metadata.frame_number = 24
        capture._publish(source.get_latest_frames())
        capture._publish(source.get_latest_frames())
        assert capture.shm.latest_multiframe_number == 1
        assert int(capture.shm.get_latest_multiframe()["0001"].frame_metadata.frame_number[0]) == 1
        # Owned snapshots remain unchanged after later publications.
        assert int(first.frame_metadata.frame_number[0]) == 0
    finally:
        capture.close_transport()
        capture.close_transport()
    assert not source._closed


def test_python_transport_is_reused_and_never_unlinked_by_pipeline_cleanup():
    source = CameraGroup.__new__(CameraGroup)
    source.shm = SimpleNamespace()
    capture = CaptureGroup(source, SimpleNamespace(value=False))
    assert capture.shm is source.shm
    capture.close_transport()


def test_geometry_change_is_rejected_before_advancing_transport():
    source = NativeSnapshots()
    capture = CaptureGroup(source, SimpleNamespace(value=False))
    capture._stop.set()
    capture._thread.join(timeout=2)
    try:
        changed = NativeSnapshots(rotated=True)
        changed.frame.frame_metadata.frame_number = 25
        with pytest.raises(RuntimeError, match="dimensions changed"):
            capture._publish(changed.get_latest_frames())
        assert capture.shm.latest_multiframe_number == 0
    finally:
        capture.close_transport()
def test_backend_selection_survives_app_state_encoding():
    import cbor2
    from freemocap.core.streaming.message_model import AppStateMessage, encode_message
    message = AppStateMessage.from_state_dict(server_pid=1, state={
        "camera_groups": {"group": {"backend": "rust", "alive": True}},
    })
    assert cbor2.loads(encode_message(message))["state"]["camera_groups"]["group"]["backend"] == "rust"
