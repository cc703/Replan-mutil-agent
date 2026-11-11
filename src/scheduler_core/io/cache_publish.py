"""Atomic no-replace directory publication on supported operating systems."""

import ctypes
import errno
import os
import sys
from pathlib import Path


def publish_noreplace(source: Path, destination: Path) -> None:
    """Move source to destination atomically without replacing an existing target.

    Both arguments are paths; success returns None and moves the source.
    Existing targets raise FileExistsError; other OS errors propagate as OSError.
    Windows uses MoveFileExW without replacement and Linux uses renameat2 with
    RENAME_NOREPLACE; unsupported platforms or unavailable primitives fail
    closed. Windows was exercised on the local filesystem; Linux was not tested.
    Caller validates paths and cleans up source after failure. This does not
    defend against hostile concurrent path replacement.
    """
    if sys.platform == "win32":
        _publish_windows(source, destination)
    elif sys.platform.startswith("linux"):
        _publish_linux(source, destination)
    else:
        raise OSError(errno.ENOTSUP, "atomic no-replace publication unavailable")


def _publish_windows(source: Path, destination: Path) -> None:
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    move = kernel.MoveFileExW
    move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    move.restype = wintypes.BOOL
    if not move(str(source), str(destination), 0):
        code = ctypes.get_last_error()
        if code in (80, 183):
            raise FileExistsError(code, "destination exists", str(destination))
        raise ctypes.WinError(code)


def _publish_linux(source: Path, destination: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        rename = libc.renameat2
    except AttributeError as exc:
        raise OSError(errno.ENOTSUP, "renameat2 unavailable") from exc
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))
