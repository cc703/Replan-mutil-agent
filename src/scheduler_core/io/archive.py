"""Plan and publish completed runs as deterministic archives."""

import hashlib
import os
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO

from .archive_publish import publish_noreplace
from .archive_record import (
    ArchiveEntry,
    ArchiveRecord,
    content_digest,
    parse_record,
    serialize_record,
)
from .archive_verify import VerifyResult as VerifyResult
from .archive_verify import locate
from .artifacts import ArtifactStore, _time
from .errors import ArtifactError
from .manifest import read_manifest
from .paths import check_chain, mkdir_chain
from .tree_snapshot import TreeSnapshot, scan_tree


def _stream_digest(stream: IO[bytes]) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ArchivePlan:
    """Read-only source identity and snapshot, bound to a store root."""

    run_id: str
    kind: str
    name: str
    source: Path
    zip_path: Path
    sidecar_path: Path
    size: int
    file_count: int
    snapshot: TreeSnapshot


@dataclass(frozen=True)
class ArchiveResult:
    """Publication status, target paths, and nonfatal warnings."""

    zip_path: Path
    sidecar_path: Path
    status: str
    warnings: tuple[str, ...] = ()


def plan_archive(
    store: ArtifactStore, run_id: str, kind: str | None = None, name: str | None = None
) -> ArchivePlan:
    """Inspect one completed run without writing; reject unsafe or oversized trees."""
    root = ArtifactStore.open_existing(store.root, clock=store.clock).root
    source = locate(root, "runs", run_id, kind, name)
    manifest = read_manifest(source)
    if manifest.status != "completed":
        raise ArtifactError("run is not completed")
    snapshot = scan_tree(source, max_depth=16, max_files=100000)
    if snapshot.file_count > 100000 or any(
        e.relpath.count("/") + 1 > 16 for e in snapshot.entries if e.relpath != "."
    ):
        raise ArtifactError("archive limits exceeded")
    target = root / "archive" / manifest.kind / manifest.name
    check_chain(target)
    return ArchivePlan(
        run_id,
        manifest.kind,
        manifest.name,
        source,
        target / f"{run_id}.zip",
        target / f"{run_id}.archive.json",
        snapshot.total_bytes,
        snapshot.file_count,
        snapshot,
    )


def _write_zip(stage: Path, plan: ArchivePlan) -> list[ArchiveEntry]:
    entries = []
    with zipfile.ZipFile(stage, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in plan.snapshot.entries:
            if item.kind != "file":
                continue
            info = zipfile.ZipInfo(f"{plan.run_id}/{item.relpath}", (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            setattr(info, "_compresslevel", 9)
            info.create_system = 3
            info.external_attr = 0o100444 << 16
            digest = hashlib.sha256()
            size = 0
            with (
                (plan.source / item.relpath).open("rb") as source,
                archive.open(info, "w") as output,
            ):
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                    output.write(chunk)
            entries.append(ArchiveEntry(path=item.relpath, size=size, sha256=digest.hexdigest()))
    return entries


def _check_zip(stage: Path, run_id: str, entries: list[ArchiveEntry]) -> None:
    with zipfile.ZipFile(stage) as archive:
        names = [f"{run_id}/{entry.path}" for entry in entries]
        if archive.namelist() != names or archive.testzip() is not None:
            raise ArtifactError("stage verification failed")
        for entry, name in zip(entries, names, strict=True):
            with archive.open(name) as stream:
                digest = _stream_digest(stream)
            if archive.getinfo(name).file_size != entry.size or digest != entry.sha256:
                raise ArtifactError("stage verification failed")


def _stage(parent: Path) -> Path:
    descriptor, filename = tempfile.mkstemp(prefix="stage-", suffix=".part", dir=parent)
    os.close(descriptor)
    return Path(filename)


def _make_record(
    fresh: ArchivePlan, zip_stage: Path, entries: list[ArchiveEntry], now: datetime
) -> ArchiveRecord:
    manifest_bytes = (fresh.source / "manifest.json").read_bytes()
    manifest = read_manifest(fresh.source)
    with zip_stage.open("rb") as stream:
        zip_digest = _stream_digest(stream)
    zip_size = zip_stage.stat().st_size
    parents: set[str] = set()
    for item in fresh.snapshot.entries:
        parts = item.relpath.split("/")
        parents.update("/".join(parts[:i]) for i in range(1, len(parts)))
    empty = [
        item.relpath
        for item in fresh.snapshot.entries
        if item.kind == "directory" and item.relpath != "." and item.relpath not in parents
    ]
    record = ArchiveRecord.model_validate(
        {
            "schema": 1,
            "tool_version": "c3-1",
            "run_id": fresh.run_id,
            "kind": fresh.kind,
            "name": fresh.name,
            "source_relpath": f"runs/{fresh.kind}/{fresh.name}/{fresh.run_id}",
            "status": "completed",
            "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "git_commit": manifest.git.commit,
            "git_dirty": manifest.git.dirty,
            "archived_at": now,
            "archive_filename": fresh.zip_path.name,
            "archive_sha256": zip_digest,
            "archive_bytes": zip_size,
            "file_count": len(entries),
            "content_sha256": content_digest(entries),
            "entries": entries,
            "empty_directories": empty,
        }
    )
    return record


def _rollback_zip(path: Path, identity: tuple[int, int] | None, digest: str) -> bool:
    """Remove only a published file whose identity and digest remain ours."""
    try:
        check_chain(path)
        info = path.stat()
        with path.open("rb") as stream:
            current_digest = _stream_digest(stream)
        if (info.st_dev, info.st_ino) != identity or current_digest != digest:
            return False
        path.unlink()
        return True
    except (OSError, ArtifactError):
        return False


def apply_archive(store: ArtifactStore, plan: ArchivePlan, now: datetime) -> ArchiveResult:
    """Revalidate a plan and publish two files without replacing existing targets.

    The source is read only. Failure raises ArtifactError, except a failed
    rollback returns PARTIAL_ARCHIVE. Hostile concurrent changes are not guarded.
    """
    now = _time(now)
    fresh = plan_archive(store, plan.run_id, plan.kind, plan.name)
    if fresh != plan:
        raise ArtifactError("SOURCE_CHANGED")
    for path in (fresh.zip_path, fresh.sidecar_path):
        check_chain(path)
        if path.exists():
            raise ArtifactError("ARCHIVE_EXISTS")
    mkdir_chain(store.root, fresh.zip_path.parent)
    stages: list[tuple[Path, tuple[int, int]]] = []
    published = False
    identity = None
    zip_digest = ""
    try:
        zip_stage = _stage(fresh.zip_path.parent)
        stage_info = zip_stage.stat()
        stages.append((zip_stage, (stage_info.st_dev, stage_info.st_ino)))
        entries = _write_zip(zip_stage, fresh)
        _check_zip(zip_stage, fresh.run_id, entries)
        if plan_archive(store, plan.run_id, plan.kind, plan.name) != fresh:
            raise ArtifactError("SOURCE_CHANGED")
        record = _make_record(fresh, zip_stage, entries, now)
        zip_digest = record.archive_sha256
        side_stage = _stage(fresh.zip_path.parent)
        stage_info = side_stage.stat()
        stages.append((side_stage, (stage_info.st_dev, stage_info.st_ino)))
        serialized = serialize_record(record)
        side_stage.write_bytes(serialized)
        if parse_record(side_stage.read_bytes()) != record:
            raise ArtifactError("sidecar stage verification failed")
        check_chain(fresh.zip_path)
        check_chain(fresh.sidecar_path)
        if plan_archive(store, plan.run_id, plan.kind, plan.name) != fresh:
            raise ArtifactError("SOURCE_CHANGED")
        publish_noreplace(zip_stage, fresh.zip_path)
        published = True
        info = fresh.zip_path.stat()
        identity = (info.st_dev, info.st_ino)
        publish_noreplace(side_stage, fresh.sidecar_path)
    except (OSError, ValueError, zipfile.BadZipFile, ArtifactError) as exc:
        if published and not _rollback_zip(fresh.zip_path, identity, zip_digest):
            return ArchiveResult(fresh.zip_path, fresh.sidecar_path, "PARTIAL_ARCHIVE")
        if isinstance(exc, ArtifactError):
            raise
        raise ArtifactError("archive publication failed") from exc
    finally:
        for stage, stage_identity in stages:
            try:
                check_chain(stage)
                if stage.exists():
                    info = stage.stat()
                    if (info.st_dev, info.st_ino) == stage_identity:
                        stage.unlink()
            except (OSError, ArtifactError):
                pass
    warnings = []
    for path in (fresh.zip_path, fresh.sidecar_path):
        try:
            os.chmod(path, 0o444)
        except OSError:
            warnings.append("READONLY_NOT_APPLIED")
    return ArchiveResult(
        fresh.zip_path, fresh.sidecar_path, "ARCHIVED", tuple(sorted(set(warnings)))
    )
