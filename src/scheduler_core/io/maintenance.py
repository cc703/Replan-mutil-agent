"""Bound, read-only planning and guarded cleanup orchestration."""

import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .artifacts import ArtifactStore, _time
from .errors import ArtifactError, UnsafePathError
from .index_refs import read_index
from .manifest import read_manifest
from .paths import _is_link, check_chain, relative_path
from .removal import remove_tree
from .retention import CleanupItem, CleanupKind, CleanupPlan, CleanupResult, parse_age
from .tree_snapshot import scan_tree

if TYPE_CHECKING:
    from .archive import ArchivePlan, ArchiveResult, VerifyResult


def _ns(value: datetime) -> int:
    delta = _time(value) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return ((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds) * 1000


def _children(path: Path) -> list[Path]:
    check_chain(path)
    if not path.exists():
        return []
    if not path.is_dir() or _is_link(path):
        raise UnsafePathError(f"unsafe directory: {path}")
    return sorted(path.iterdir())


def _remaining(path: Path) -> list[Path]:
    """List remaining nodes without descending into linked directories."""
    result = [path]
    if _is_link(path) or not path.is_dir():
        return result
    for child in sorted(path.iterdir()):
        result.extend(_remaining(child))
    return result


def _runs(root: Path) -> list[Path]:
    result: list[Path] = []
    for kind in _children(root / "runs"):
        if (
            kind.name not in {"experiment", "sim", "agent_eval"}
            or not kind.is_dir()
            or _is_link(kind)
        ):
            result.append(kind)
            continue
        for name in _children(kind):
            if not name.is_dir() or _is_link(name):
                result.append(name)
                continue
            result.extend(_children(name))
    return result


def _item(path: Path, now_ns: int, age: int, *, run: bool, refs: object) -> CleanupItem:
    from .index_refs import IndexReferences

    assert isinstance(refs, IndexReferences)
    blank = CleanupItem(path, None, None, 0, 0, False, "NOT_A_RUN", None)
    try:
        relative_path(path.name, reserved=False)
    except UnsafePathError:
        return replace(blank, reason="BAD_NAME")
    if run and (
        not path.is_dir()
        or _is_link(path)
        or len(path.parts) < 4
        or path.parent.parent.name not in {"experiment", "sim", "agent_eval"}
    ):
        return blank
    try:
        snapshot = scan_tree(path)
    except UnsafePathError:
        return replace(blank, reason="UNSAFE_ENTRY")
    except OSError:
        return replace(blank, reason="UNSAFE_ENTRY")
    basis = snapshot.last_activity_ns
    referenced = False
    if run:
        try:
            manifest = read_manifest(path)
        except ArtifactError:
            return replace(
                blank,
                reason="MANIFEST_INVALID",
                snapshot=snapshot,
                size=snapshot.total_bytes,
                file_count=snapshot.file_count,
            )
        if manifest.status == "completed":
            return replace(
                blank,
                reason="COMPLETED",
                snapshot=snapshot,
                size=snapshot.total_bytes,
                file_count=snapshot.file_count,
            )
        if manifest.status == "running":
            basis = _ns(manifest.started_at)
            reason = "STALE_RUNNING" if now_ns - basis > 14 * 86400 * 1000000000 else "RUNNING"
            return CleanupItem(
                path,
                basis,
                now_ns - basis,
                snapshot.total_bytes,
                snapshot.file_count,
                False,
                reason,
                snapshot,
            )
        assert manifest.ended_at is not None
        basis = _ns(manifest.ended_at)
        referenced = refs.protects(manifest.kind, manifest.name, manifest.run_id)
    elapsed = now_ns - basis
    reason = (
        "FUTURE_TIME"
        if elapsed < 0
        else "PROTECTED"
        if referenced
        else "ELIGIBLE"
        if elapsed > age
        else "TOO_YOUNG"
    )
    return CleanupItem(
        path,
        basis,
        elapsed,
        snapshot.total_bytes,
        snapshot.file_count,
        referenced,
        reason,
        snapshot,
    )


class Maintenance:
    """Operations bound to an existing ArtifactStore; plans grant no authority."""

    def __init__(self, store: ArtifactStore) -> None:
        self._store = store

    def plan_cleanup(
        self, kind: CleanupKind, older_than: str | None, index: Path, now: datetime | None = None
    ) -> CleanupPlan:
        """Return a read-only plan for kind and age, using an aware UTC clock.

        None selects the kind's default age; invalid ages raise ValueError.
        Unsafe roots or an unreadable index raise ArtifactError without writing.
        """
        if kind not in {"tmp", "failed-runs"}:
            raise ValueError("invalid cleanup kind")
        root = ArtifactStore.open_existing(self._store.root, clock=self._store.clock).root
        current = _time(now if now is not None else self._store.clock())
        duration = older_than if older_than is not None else ("7d" if kind == "tmp" else "14d")
        age = parse_age(duration, kind)
        runs = _runs(root)
        check_chain(index)
        run_ids: set[str] = set()
        for path in runs:
            try:
                run_ids.add(read_manifest(path).run_id)
            except ArtifactError:
                continue
        refs = read_index(Path(os.path.abspath(index)), run_ids)
        paths = _children(root / "tmp") if kind == "tmp" else runs
        items = tuple(
            _item(path, _ns(current), age, run=kind == "failed-runs", refs=refs) for path in paths
        )
        return CleanupPlan(
            kind,
            duration,
            current,
            Path(os.path.abspath(index)),
            items,
            refs.absent,
            "INDEX_ABSENT" if refs.absent else "INDEX_OK",
        )

    def apply_cleanup(
        self, plan: CleanupPlan, index: Path, now: datetime | None = None
    ) -> CleanupResult:
        """Return deletion outcomes after rechecking the supplied plan and index.

        Only still-eligible bound-store candidates are deleted. Invalid input
        raises ValueError or ArtifactError; individual deletion failures are reported.
        Concurrent malicious modifications are not fully prevented.
        """
        self.plan_cleanup(plan.kind, plan.older_than, index, now)
        deleted: list[Path] = []
        skipped: list[CleanupItem] = []
        failed: list[Path] = []
        partial: list[Path] = []
        remaining: list[Path] = []
        for old in sorted(plan.items, key=lambda item: item.path):
            if old.reason != "ELIGIBLE":
                skipped.append(old)
                continue
            # Re-read index and the candidate immediately before each removal.
            latest = self.plan_cleanup(plan.kind, plan.older_than, index, now)
            item = next(
                (candidate for candidate in latest.items if candidate.path == old.path), None
            )
            if (
                item is None
                or item.reason != "ELIGIBLE"
                or item.snapshot != old.snapshot
                or item.basis_ns != old.basis_ns
            ):
                skipped.append(replace(old, reason="CHANGED_SINCE_PLAN"))
                continue
            try:
                remove_tree(self._store.root, item.path, item.snapshot)
                deleted.append(item.path)
            except (OSError, ArtifactError):
                failed.append(item.path)
                if os.path.lexists(item.path):
                    try:
                        if scan_tree(item.path) != item.snapshot:
                            partial.append(item.path)
                    except (OSError, ArtifactError):
                        partial.append(item.path)
                    try:
                        remaining.extend(_remaining(item.path))
                    except (OSError, ArtifactError):
                        remaining.append(item.path)
        return CleanupResult(
            tuple(deleted), tuple(skipped), tuple(failed), tuple(partial), tuple(remaining)
        )

    def plan_archive(
        self, run_id: str, kind: str | None = None, name: str | None = None
    ) -> "ArchivePlan":
        """Return a read-only plan for one completed run or raise ArtifactError."""
        from .archive import plan_archive

        return plan_archive(self._store, run_id, kind, name)

    def archive(self, plan: "ArchivePlan", now: datetime | None = None) -> "ArchiveResult":
        """Return the archive result after revalidating the plan and aware time."""
        from .archive import apply_archive

        return apply_archive(
            self._store, plan, _time(now if now is not None else self._store.clock())
        )

    def verify_archive(
        self, run_id: str, kind: str | None = None, name: str | None = None
    ) -> "VerifyResult":
        """Return archive verification results without extracting or writing."""
        from .archive_verify import verify_archive

        return verify_archive(self._store, run_id, kind, name)
