"""Age parsing and immutable cleanup reports."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from .tree_snapshot import TreeSnapshot

CleanupKind = Literal["tmp", "failed-runs"]


@dataclass(frozen=True)
class CleanupItem:
    """One inspected cleanup candidate and its justification."""

    path: Path
    basis_ns: int | None
    age_ns: int | None
    size: int
    file_count: int
    referenced: bool
    reason: str
    snapshot: TreeSnapshot | None


@dataclass(frozen=True)
class CleanupPlan:
    """Read-only snapshot of a cleanup request."""

    kind: CleanupKind
    older_than: str
    now: datetime
    index: Path
    items: tuple[CleanupItem, ...]
    index_absent: bool
    index_status: str

    @property
    def protected(self) -> tuple[CleanupItem, ...]:
        """Return items protected by an index reference."""
        return tuple(item for item in self.items if item.reason == "PROTECTED")

    @property
    def stale_running(self) -> tuple[CleanupItem, ...]:
        """Return old running items, which are never automatically removed."""
        return tuple(item for item in self.items if item.reason == "STALE_RUNNING")


@dataclass(frozen=True)
class CleanupResult:
    """Deletion outcomes and remaining paths after partial failures."""

    deleted: tuple[Path, ...]
    skipped: tuple[CleanupItem, ...]
    failed: tuple[Path, ...]
    partial: tuple[Path, ...]
    remaining: tuple[Path, ...]


def parse_age(value: str, kind: CleanupKind) -> int:
    """Parse a bounded duration into integer nanoseconds."""
    if not re.fullmatch(r"[1-9][0-9]*[smhdw]", value, flags=re.ASCII):
        raise ValueError("invalid age")
    seconds = int(value[:-1]) * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[value[-1]]
    if seconds > 3650 * 86400 or (kind == "failed-runs" and seconds < 14 * 86400):
        raise ValueError("age outside permitted range")
    return seconds * 1_000_000_000
