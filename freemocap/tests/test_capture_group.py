"""CaptureGroup is one view of either camera backend's group: SkellyCam's shared memory, errors and previews.

Both backends fill SkellyCam shared memory at SkellyCam frame numbers, so the pipeline reads the group's own memory
and never copies, renumbers or releases it.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.rust_camera_group import RustCameraGroup
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from freemocap.core.pipeline.realtime.capture_group import CaptureGroup


def opencv_group():
    group = CameraGroup.__new__(CameraGroup)
    group.shm = Mock()
    group.transport_error = None
    group.get_frontend_payload_by_frame_number = Mock(return_value=(memoryview(b"preview"), 1.0))
    return group


def rust_group():
    config = CameraConfig(camera_id="0001", camera_index=0)
    group = RustCameraGroup("g", {"0001": config}, SimpleNamespace(list_groups=lambda: ["g"]))
    group._shm = Mock(spec=CameraGroupSharedMemory)  # as the pixel builder leaves it once trackers read frames
    group.get_frontend_payload_by_frame_number = Mock(return_value=(memoryview(b"preview"), 1.0))
    return group


@pytest.mark.parametrize("make_group", [opencv_group, rust_group], ids=["opencv", "rust"])
def test_pipeline_reads_the_groups_own_shared_memory_and_never_releases_it(make_group):
    group = make_group()
    capture = CaptureGroup(group, SimpleNamespace(value=False))
    assert capture.shm is group.shm
    assert capture.error is None
    assert capture.get_frontend_payload_by_frame_number(7, {"0001": {"width": 10, "height": 10}})[1] == 1.0
    group.get_frontend_payload_by_frame_number.assert_called_once_with(7, {"0001": {"width": 10, "height": 10}})
    capture.close_transport()
    capture.close_transport()
    assert capture.get_frontend_payload_by_frame_number(8) is None
    group.shm.unlink_and_close.assert_not_called()
    group.shm.unlink.assert_not_called()


@pytest.mark.parametrize("make_group", [opencv_group, rust_group], ids=["opencv", "rust"])
def test_a_group_that_stops_delivering_frames_reports_why(make_group):
    group = make_group()
    capture = CaptureGroup(group, SimpleNamespace(value=False))
    group.transport_error = "RuntimeError: camera 0001: JPEG decode failed"
    assert capture.error == "RuntimeError: camera 0001: JPEG decode failed"
