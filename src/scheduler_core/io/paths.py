"""Path validation and atomic file operations for run storage."""

import os
import re
import stat
import tempfile
from pathlib import Path

from .errors import UnsafePathError


_RESERVED = {"con", "prn", "aux", "nul"} | {
    f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)
}


def relative_path(value: str, *, reserved: bool = True) -> Path:
    """Validate a POSIX relative artifact path, returning its path object."""
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise UnsafePathError("invalid relative path")
    parts = value.split("/")
    for part in parts:
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", part)
            or part.endswith(".")
            or ".." in part
            or re.search(r"~[0-9]", part)
            or part.split(".")[0] in _RESERVED
            or (reserved and part in {"manifest.json", "config.yaml"})
        ):
            raise UnsafePathError(f"unsafe path component: {part!r}")
    return Path(*parts)


def _is_link(path: Path) -> bool:
    info = path.lstat()
    return (
        stat.S_ISLNK(info.st_mode)
        or bool(
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
        )
        or (stat.S_ISREG(info.st_mode) and info.st_nlink > 1)
    )


def check_chain(path: Path) -> None:
    """Reject links in every existing component of an absolute path."""
    absolute = path if path.is_absolute() else Path.cwd() / path
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            if _is_link(current):
                raise UnsafePathError(f"link in path: {current}")
        except FileNotFoundError:
            continue


def inside(root: Path, path: Path) -> None:
    """Check both original chain and resolved containment."""
    check_chain(root)
    check_chain(path)
    if not path.resolve().is_relative_to(root.resolve()):
        raise UnsafePathError("path escapes root")


def mkdir_chain(root: Path, path: Path) -> None:
    """Create a checked directory chain without following known links."""
    inside(root, path)
    for component in reversed((path, *path.parents)):
        if component == root or component.is_relative_to(root):
            component.mkdir(exist_ok=True)
            inside(root, component)


def atomic_write(path: Path, data: bytes, *, readonly: bool = False) -> None:
    """Replace a file atomically; a failed write preserves its prior bytes."""
    fd, name = tempfile.mkstemp(prefix=".manifest-" if readonly else ".part-", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if readonly:
            os.chmod(temp, 0o444)
        os.replace(temp, path)
    except BaseException:
        try:
            os.chmod(temp, 0o666)
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
