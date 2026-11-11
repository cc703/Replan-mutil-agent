"""Read-only, link-rejecting snapshots of artifact trees."""

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .errors import UnsafePathError
from .paths import _is_link, check_chain, relative_path


@dataclass(frozen=True)
class TreeEntry:
    """Identity and metadata of a single ordinary file or directory."""

    relpath: str
    kind: Literal["file", "directory"]
    size: int
    mtime_ns: int
    mode: int
    device: int
    inode: int


@dataclass(frozen=True)
class TreeSnapshot:
    """Sorted tree metadata, including the root as ``.``."""

    root: Path
    entries: tuple[TreeEntry, ...]

    @property
    def total_bytes(self) -> int:
        """Return the sum of ordinary file sizes."""
        return sum(entry.size for entry in self.entries if entry.kind == "file")

    @property
    def file_count(self) -> int:
        """Return the number of ordinary files."""
        return sum(entry.kind == "file" for entry in self.entries)

    @property
    def last_activity_ns(self) -> int:
        """Return the most recent modification time in the tree."""
        return max(entry.mtime_ns for entry in self.entries)


def scan_tree(
    root: Path, *, max_depth: int | None = None, max_files: int | None = None
) -> TreeSnapshot:
    """Snapshot a safe existing tree; reject links and nonordinary entries.

    Root has depth zero. Optional nonnegative integer limits bound descendant
    depth and ordinary file count; bool, negative or noninteger limits raise
    ValueError. Exceeding a limit or unsafe entries raises UnsafePathError.
    The read-only inspection cannot prevent concurrent filesystem changes.
    """
    for limit in (max_depth, max_files):
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError("tree limits must be nonnegative integers")
    check_chain(root)
    root = Path(os.path.abspath(root))
    check_chain(root)
    entries: list[TreeEntry] = []
    files = 0

    def visit(path: Path, relpath: str, depth: int) -> None:
        nonlocal files
        if max_depth is not None and depth > max_depth:
            raise UnsafePathError("tree depth limit exceeded")
        info = path.lstat()
        if _is_link(path):
            raise UnsafePathError(f"link or hardlink: {path}")
        if stat.S_ISDIR(info.st_mode):
            kind: Literal["file", "directory"] = "directory"
        elif stat.S_ISREG(info.st_mode):
            kind = "file"
            files += 1
            if max_files is not None and files > max_files:
                raise UnsafePathError("tree file count limit exceeded")
        else:
            raise UnsafePathError(f"nonordinary entry: {path}")
        entries.append(
            TreeEntry(
                relpath,
                kind,
                info.st_size,
                info.st_mtime_ns,
                info.st_mode,
                info.st_dev,
                info.st_ino,
            )
        )
        if kind == "directory":
            with os.scandir(path) as children:
                names = sorted(child.name for child in children)
            for name in names:
                relative_path(name, reserved=False)
                visit(path / name, name if relpath == "." else f"{relpath}/{name}", depth + 1)

    visit(root, ".", 0)
    return TreeSnapshot(root, tuple(sorted(entries, key=lambda entry: entry.relpath)))
