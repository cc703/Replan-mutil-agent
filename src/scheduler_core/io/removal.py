"""Guarded bottom-up removal of inspected cleanup targets."""

import os
import stat
from pathlib import Path

from .errors import UnsafePathError
from .paths import _is_link, inside
from .tree_snapshot import TreeSnapshot, scan_tree


def remove_tree(root: Path, target: Path, snapshot: TreeSnapshot | None) -> None:
    """Delete a matching tree without following links or touching its parent.

    Raises UnsafePathError if the tree differs or escapes root, and OSError on
    deletion failure. Concurrent hostile filesystem changes remain possible.
    """
    inside(root, target)
    if target == root or snapshot is None or scan_tree(target) != snapshot:
        raise UnsafePathError("tree changed before deletion")
    entries = sorted(
        snapshot.entries,
        key=lambda entry: (
            entry.relpath == "manifest.json",
            -entry.relpath.count("/"),
            entry.relpath,
        ),
    )
    # Keep every directory until all ordinary files, including the manifest, are removed.
    files = [entry for entry in entries if entry.kind == "file"]
    directories = sorted(
        (entry for entry in entries if entry.kind == "directory"),
        key=lambda entry: (-entry.relpath.count("/"), entry.relpath == ".", entry.relpath),
    )
    for entry in [*files, *directories]:
        path = target if entry.relpath == "." else target / entry.relpath
        inside(root, path)
        if not (path == target or path.is_relative_to(target)) or _is_link(path):
            raise UnsafePathError("unsafe removal path")
        info = path.lstat()
        if (info.st_dev, info.st_ino) != (entry.device, entry.inode):
            raise UnsafePathError("entry changed")
        if entry.kind == "file":
            if not stat.S_ISREG(info.st_mode):
                raise UnsafePathError("entry changed type")
            os.chmod(path, info.st_mode | stat.S_IWRITE)
            os.unlink(path)
        else:
            if not stat.S_ISDIR(info.st_mode):
                raise UnsafePathError("entry changed type")
            os.rmdir(path)
