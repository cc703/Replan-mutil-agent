"""Windows ordinary-file publication without replacement."""

import ctypes
import errno
import sys
from pathlib import Path


def publish_noreplace(source: Path, destination: Path) -> None:
    """Atomically move a file without replacement; unsupported systems fail closed."""
    if sys.platform != "win32":
        raise OSError(errno.ENOTSUP, "ordinary-file publication unverified")
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
