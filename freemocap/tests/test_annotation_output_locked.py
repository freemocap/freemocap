"""Actionable publication failures, without replacing or copying locked videos."""
import ctypes
import errno
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from freemocap.core.pipeline.posthoc.annotation_output import AnnotationVideoOutput


def output_ready_to_publish(tmp_path):
    output = object.__new__(AnnotationVideoOutput)
    output.request = SimpleNamespace(video=SimpleNamespace(frame_count=1))
    output.frames_written = 1
    output.writer = Mock()
    output.base_reader = None
    output.destination = tmp_path / 'camera.annotated.mp4'
    output.temporary = tmp_path / '.camera.partial.mp4'
    output.destination.write_bytes(b'existing video')
    output.temporary.write_bytes(b'new video')
    return output


def test_permission_error_explains_how_to_retry(tmp_path, monkeypatch):
    output = output_ready_to_publish(tmp_path)
    writer = output.writer
    original = PermissionError(errno.EACCES, 'Access denied')
    def denied(*args):
        raise original
    monkeypatch.setattr(Path, 'replace', denied)
    with pytest.raises(PermissionError, match='Is this recording open in Blender') as caught:
        output.publish()
    assert str(output.destination) in str(caught.value)
    assert 'retry processing' in str(caught.value)
    assert caught.value.__cause__ is original
    writer.release.assert_called_once()
    assert output.destination.read_bytes() == b'existing video'
    output.close()
    assert not output.temporary.exists()


def test_unrelated_io_error_is_not_reported_as_a_lock(tmp_path, monkeypatch):
    output = output_ready_to_publish(tmp_path)
    original = OSError(errno.ENOSPC, 'No space left')
    def failed(*args):
        raise original
    monkeypatch.setattr(Path, 'replace', failed)
    with pytest.raises(OSError) as caught:
        output.publish()
    assert caught.value is original
    output.close()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows file-sharing semantics')
def test_actual_windows_lock_then_successful_retry(tmp_path):
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    output = output_ready_to_publish(tmp_path)
    # Open for reading without FILE_SHARE_DELETE, like a consumer holding media.
    handle = create(str(output.destination), 0x80000000, 1, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    try:
        with pytest.raises(PermissionError, match='Close the recording in Blender'):
            output.publish()
        assert output.destination.read_bytes() == b'existing video'
    finally:
        assert close(handle)
        output.close()
    retry = output_ready_to_publish(tmp_path)
    retry.publish()
    assert retry.destination.read_bytes() == b'new video'
    assert not retry.temporary.exists()
    retry.close()
