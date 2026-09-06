"""Read a committed file while permitting atomic replacement on Windows."""

from contextlib import contextmanager
from collections.abc import Iterator
import ctypes
from ctypes import wintypes
import os
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
        if not _replace_file(str(destination), str(source), None, 0, None, None):
            raise ctypes.WinError(ctypes.get_last_error())
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
