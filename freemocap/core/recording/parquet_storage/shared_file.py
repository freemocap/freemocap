"""Read a committed file while permitting atomic replacement on Windows."""

from contextlib import contextmanager
from collections.abc import Iterator
import ctypes
from ctypes import wintypes
import os
import logging
import time
from pathlib import Path
from typing import BinaryIO

if os.name == "nt":
    import msvcrt

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _create_file = _kernel.CreateFileW
    _create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    _create_file.restype = wintypes.HANDLE
    _close_handle = _kernel.CloseHandle
    _close_handle.argtypes = (wintypes.HANDLE,)
    _close_handle.restype = wintypes.BOOL
    _replace_file = _kernel.ReplaceFileW
    _replace_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    _replace_file.restype = wintypes.BOOL


def replace_recording_file(*, source: Path, destination: Path) -> None:
    if os.name == "nt" and destination.exists():
        delays = (0.01, 0.05, 0.1, 0.25, 0.5)
        for attempt in range(len(delays) + 1):
            if _replace_file(str(destination), str(source), None, 0, None, None):
                return
            error = ctypes.get_last_error()
            # 1175 preserves both original names; 1176/1177 can change them and
            # must never be retried as though the same inputs still exist.
            # [@microsoftReplaceFileW]
            if error != 1175 or attempt == len(delays):
                raise ctypes.WinError(error)
            logging.getLogger(__name__).warning(
                "Windows deferred recording replacement (1175); retry %s/%s in %.2f s: %s",
                attempt + 1, len(delays), delays[attempt], destination)
            time.sleep(delays[attempt])
    else:
        os.replace(source, destination)


@contextmanager
def shared_recording_file(path: Path) -> Iterator[BinaryIO]:
    if os.name != "nt":
        with path.open("rb") as stream:
            yield stream
        return
    # GENERIC_READ, FILE_SHARE_READ | WRITE | DELETE, OPEN_EXISTING, NORMAL.
    handle = _create_file(str(path), 0x80000000, 0x1 | 0x2 | 0x4, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        _close_handle(handle)
        raise
    with os.fdopen(descriptor, "rb") as stream:
        yield stream
